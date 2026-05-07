"""Periodic username monitoring with change detection.

Usage::

    watcher = Watcher(username, interval_hours=24, include_migrated=False)
    await watcher.run()  # blocks, runs every N hours
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from clawithme.cache import ResultCache
from clawithme.cli import load_all_sites
from clawithme.config import load_config
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import load_engines
from clawithme.engine.proxy_manager import ProxyManager
from clawithme.logging import get_logger, new_trace_id
from clawithme.signals.llm_verifier import LLMVerifier

if TYPE_CHECKING:
    from clawithme.pipeline import SearchResult

logger = get_logger()

_CACHE_DIR = Path.home() / ".cache" / "clawithme"


@dataclass
class WatchChange:
    """A single detected change between two watch runs."""

    change_type: str  # "new_site", "lost_site", "profile_update", "new_leak"
    site_id: str = ""
    site_name: str = ""
    url: str = ""
    detail: str = ""  # human-readable description


@dataclass
class WatchReport:
    """Aggregated changes for a watch run."""

    username: str
    timestamp: float
    run_hits: int = 0
    run_profiles: int = 0
    run_leaks: int = 0
    changes: list[WatchChange] = field(default_factory=list)
    is_baseline: bool = False  # True for the first run (no baseline to compare)

    @property
    def has_changes(self) -> bool:
        return len(self.changes) > 0

    @property
    def new_sites(self) -> list[WatchChange]:
        return [c for c in self.changes if c.change_type == "new_site"]

    @property
    def lost_sites(self) -> list[WatchChange]:
        return [c for c in self.changes if c.change_type == "lost_site"]

    @property
    def profile_updates(self) -> list[WatchChange]:
        return [c for c in self.changes if c.change_type == "profile_update"]

    @property
    def new_leaks(self) -> list[WatchChange]:
        return [c for c in self.changes if c.change_type == "new_leak"]


class Watcher:
    """Periodic username monitor.

    Runs a full search pipeline on each tick, compares against
    the previous baseline, and reports changes to console.

    Baseline is stored in the same SQLite cache as probe results
    (``~/.cache/clawithme/cache.db``, key prefix ``watch:baseline:``).
    """

    def __init__(
        self,
        username: str,
        *,
        interval_hours: int = 24,
        include_migrated: bool = False,
        webhook_url: str | None = None,
    ) -> None:
        self._username = username
        self._interval = interval_hours * 3600
        self._include_migrated = include_migrated
        self._webhook_url = webhook_url
        self._cache = ResultCache(str(_CACHE_DIR))

    @property
    def _baseline_key(self) -> str:
        return f"watch:baseline:{self._username}"

    async def run(self) -> None:
        """Start the watch loop. Blocks until interrupted."""
        cfg = load_config()
        log = get_logger()

        print()
        print("╔══════════════════════════════════════════════════════╗")
        print(f"║  🔭 clawithme watch: {self._username:<30s} ║")
        print(f"║  Interval: {self._interval // 3600}h                              ║")
        print(f"║  Ctrl+C to stop                                      ║")
        print("╚══════════════════════════════════════════════════════╝")
        print()

        while True:
            start = time.monotonic()
            trace_id = new_trace_id()
            timestamp = datetime.now(timezone.utc).isoformat()

            print(f"\n── {timestamp} ──")
            print(f"   trace_id: {trace_id}")

            try:
                report = await self._tick(cfg)
            except (OSError, ValueError, TimeoutError, RuntimeError) as e:
                log.warning("watch_tick_failed", error=str(e))
                print(f"   ⚠️  Watch tick failed: {e}")
                await asyncio.sleep(60)
                continue

            self._print_report(report)
            if self._webhook_url:
                await self._send_webhook(report)

            elapsed = time.monotonic() - start
            wait = max(60, self._interval - elapsed)
            next_time = datetime.now(timezone.utc).isoformat()
            print(f"\n   ⏳ Next check at ~{next_time} (in {wait / 3600:.1f}h)")
            print(f"   (Elapsed: {elapsed:.1f}s, sleeping: {wait:.0f}s)")
            await asyncio.sleep(wait)

    async def _tick(self, cfg) -> WatchReport:
        """Run one full search and compare to baseline."""
        # Pre-load resources
        try:
            sites = load_all_sites(include_migrated=self._include_migrated)
        except (OSError, json.JSONDecodeError) as e:
            print(f"   ❌ Failed to load sites: {e}")
            raise
        engines = load_engines(proxy_manager=ProxyManager(cfg))
        extractors = discover_extractors()

        # LLM
        llm = LLMVerifier()
        llm_verifier = llm if llm.is_configured() else None

        # Run pipeline
        # First tick is full search, subsequent ticks use incremental
        # (stale cache → instant for known sites, probe only newcomers)
        is_first_tick = self._load_baseline() is None

        from clawithme.pipeline import AsyncPipeline
        pipeline = AsyncPipeline(
            sites, engines, extractors, cfg,
            cache=self._cache, llm_verifier=llm_verifier,
            incremental=not is_first_tick,
        )
        result = await pipeline.run(self._username)

        # Build current snapshot
        current = {
            "timestamp": time.time(),
            "hits": [
                {"site_id": h["site_id"], "site_name": h["site_name"], "url": h.get("url", "")}
                for h in result.hits
            ],
            "profiles": sorted([
                {
                    "site_id": p.get("site_id", ""),
                    "display_name": p.get("display_name", ""),
                    "bio": p.get("bio", ""),
                    "location": p.get("location", ""),
                    "follower_count": p.get("follower_count"),
                    "following_count": p.get("following_count"),
                    "post_count": p.get("post_count"),
                    "email": p.get("email", ""),
                    "phone": p.get("phone", ""),
                }
                for p in result.profiles
            ], key=lambda p: p["site_id"]),
            "leaks": sorted([
                {
                    "source": getattr(r, "source", ""),
                    "email": getattr(r, "email", ""),
                    "phone": getattr(r, "phone", ""),
                    "breach_date": getattr(r, "breach_date", ""),
                }
                for r in result.leak_records
            ], key=lambda r: f"{r.get('source','')}:{r.get('email','')}"),
        }

        # Load baseline
        baseline = self._load_baseline()

        if baseline is None:
            # First run — store baseline, no diff
            self._store_baseline(current)
            return WatchReport(
                username=self._username,
                timestamp=current["timestamp"],
                run_hits=len(result.hits),
                run_profiles=len(result.profiles),
                run_leaks=len(result.leak_records),
                is_baseline=True,
            )

        # Compare
        changes = self._diff(baseline, current)

        # Store new baseline
        self._store_baseline(current)

        return WatchReport(
            username=self._username,
            timestamp=current["timestamp"],
            run_hits=len(result.hits),
            run_profiles=len(result.profiles),
            run_leaks=len(result.leak_records),
            changes=changes,
        )

    # ── Baseline storage ───────────────────────────────────────

    def _load_baseline(self) -> dict | None:
        """Load previous watch baseline from cache."""
        cached = self._cache.get(self._baseline_key)
        if cached is None:
            return None
        return cached.get("data")

    def _store_baseline(self, data: dict) -> None:
        """Store watch baseline to cache (30-day TTL)."""
        self._cache.set(
            self._baseline_key,
            {"data": data},
            ttl_seconds=30 * 86400,  # 30 days
        )

    # ── Diff engine ────────────────────────────────────────────

    @staticmethod
    def _diff(baseline: dict, current: dict) -> list[WatchChange]:
        """Compare current snapshot to baseline, return list of changes."""
        changes: list[WatchChange] = []

        # ── Site hits ──
        baseline_ids = {h["site_id"] for h in baseline.get("hits", [])}
        current_ids = {h["site_id"] for h in current.get("hits", [])}

        for h in current.get("hits", []):
            if h["site_id"] not in baseline_ids:
                changes.append(WatchChange(
                    change_type="new_site",
                    site_id=h["site_id"],
                    site_name=h["site_name"],
                    url=h.get("url", ""),
                    detail=f"New site found: {h['site_name']} → {h.get('url', '')}",
                ))

        for h in baseline.get("hits", []):
            if h["site_id"] not in current_ids:
                changes.append(WatchChange(
                    change_type="lost_site",
                    site_id=h["site_id"],
                    site_name=h["site_name"],
                    url=h.get("url", ""),
                    detail=f"Site no longer found: {h['site_name']}",
                ))

        # ── Profile changes ──
        baseline_profiles = {p["site_id"]: p for p in baseline.get("profiles", [])}
        current_profiles = {p["site_id"]: p for p in current.get("profiles", [])}

        tracked_fields = [
            ("display_name", "显示名"),
            ("bio", "简介"),
            ("location", "位置"),
            ("follower_count", "粉丝数"),
            ("following_count", "关注数"),
            ("post_count", "帖子数"),
            ("email", "邮箱"),
            ("phone", "电话"),
        ]

        for sid, cp in current_profiles.items():
            bp = baseline_profiles.get(sid)
            if bp is None:
                continue
            diffs = []
            for field, label in tracked_fields:
                old_val = bp.get(field)
                new_val = cp.get(field)
                if old_val != new_val and (old_val or new_val):
                    diffs.append(f"{label}: {_fmt(old_val)} → {_fmt(new_val)}")
            if diffs:
                changes.append(WatchChange(
                    change_type="profile_update",
                    site_id=sid,
                    site_name=sid,
                    detail=f"Profile changed on {sid}: {'; '.join(diffs)}",
                ))

        # ── Leak records ──
        baseline_leak_keys = {
            f"{r.get('source','')}:{r.get('email','')}:{r.get('phone','')}"
            for r in baseline.get("leaks", [])
        }
        for r in current.get("leaks", []):
            key = f"{r.get('source','')}:{r.get('email','')}:{r.get('phone','')}"
            if key not in baseline_leak_keys:
                email = r.get("email", "")[:3] + "***" if r.get("email") else "N/A"
                changes.append(WatchChange(
                    change_type="new_leak",
                    site_id=r.get("source", ""),
                    site_name=r.get("source", ""),
                    detail=f"New leak: {r.get('source','')} — {email} ({r.get('breach_date','')})",
                ))

        return changes

    # ── Output ─────────────────────────────────────────────────

    @staticmethod
    def _print_report(report: WatchReport) -> None:
        """Print watch report to console."""
        print(f"   📡 Sites: {report.run_hits}  👤 Profiles: {report.run_profiles}  🔓 Leaks: {report.run_leaks}")

        if report.is_baseline:
            print("   📋 First run — baseline stored. Changes will be detected from next run.")
            return

        if not report.has_changes:
            print("   ✅ No changes detected since last run.")
            return

        print(f"\n   ═══ {len(report.changes)} change(s) detected ═══")

        for section, label in [
            ("new_sites", "🆕 New Sites"),
            ("lost_sites", "🚫 Lost Sites"),
            ("profile_updates", "📝 Profile Updates"),
            ("new_leaks", "🔓 New Leaks"),
        ]:
            items = getattr(report, section, [])
            if not items:
                continue
            print(f"\n   ── {label} ({len(items)}) ──")
            for c in items:
                print(f"      {c.detail}")

    async def _send_webhook(self, report: WatchReport) -> None:
        """POST watch report to webhook URL."""
        import urllib.request
        payload = json.dumps({
            "username": report.username,
            "timestamp": report.timestamp,
            "run_hits": report.run_hits,
            "run_profiles": report.run_profiles,
            "run_leaks": report.run_leaks,
            "changes": [
                {"type": c.change_type, "detail": c.detail}
                for c in report.changes
            ],
        }).encode()
        try:
            req = urllib.request.Request(
                self._webhook_url,
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            await asyncio.get_running_loop().run_in_executor(
                None, lambda: urllib.request.urlopen(req, timeout=10)
            )
        except (OSError, ValueError, TimeoutError) as e:
            logger.warning("webhook_failed", error=str(e))


def _fmt(val) -> str:
    """Format a value for diff display."""
    if val is None:
        return "(无)"
    s = str(val)
    return s[:60] + "..." if len(s) > 60 else s
