"""Results screen — live search results display with progress and export."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Header, LoadingIndicator, RichLog, Static

from clawithme.cache import ResultCache
from clawithme.cli import load_all_sites
from clawithme.config import load_config
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import load_engines
from clawithme.pipeline import AsyncPipeline


def _color_for_confidence(conf: float) -> str:
    if conf >= 0.75:
        return "green"
    if conf >= 0.30:
        return "yellow"
    return "red"


CONF_THRESHOLD_HIGH = 0.75
CONF_THRESHOLD_MID = 0.30


class ResultsScreen(Screen):
    """Display search results with overview, hits, profiles, clusters."""

    username = reactive("")
    hits_total = reactive(0)
    profiles_total = reactive(0)
    clusters_total = reactive(0)
    leaks_total = reactive(0)
    status_text = reactive("")

    def __init__(self) -> None:
        super().__init__()
        self._cancel_event: asyncio.Event | None = None
        self._searching = False
        self._last_result = None
        self._search_lang = "zh"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="results-layout"):
            yield Static(id="status-bar")
            yield LoadingIndicator(id="loading")
            with Horizontal(id="overview-panel"):
                yield Static("", id="stat-hits")
                yield Static("", id="stat-profiles")
                yield Static("", id="stat-clusters")
                yield Static("", id="stat-leaks")
            yield Static("🌐 Hits", classes="panel-title")
            yield RichLog(id="hits-log", highlight=True, markup=True, wrap=True)
            yield Static("👤 Profiles", classes="panel-title")
            yield RichLog(
                id="profiles-log", highlight=True, markup=True, wrap=True
            )
            yield Static("🔗 Identity Clusters", classes="panel-title")
            yield RichLog(
                id="clusters-log", highlight=True, markup=True, wrap=True
            )
            yield Static("🔓 Leak Records", classes="panel-title")
            yield RichLog(
                id="leaks-log", highlight=True, markup=True, wrap=True
            )
            with Horizontal(id="action-bar"):
                yield Button("📄 HTML", id="btn-html", variant="primary")
                yield Button("📋 JSON", id="btn-json")
                yield Button("📝 MD", id="btn-md")
                yield Button("⏹ Cancel", id="btn-cancel", variant="error")
                yield Button("🔍 New Search", id="btn-new", variant="default")

    def on_mount(self) -> None:
        """Initialize results screen."""

    def watch_status_text(self, value: str) -> None:
        self.query_one("#status-bar", Static).update(f"  {value}")

    def _upd_stat(self, wid: str, label: str, value: int) -> None:
        self.query_one(f"#{wid}", Static).update(
            f"[bold]{value}[/] {label}"
        )

    def watch_hits_total(self, value: int) -> None:
        self._upd_stat("stat-hits", "hits", value)

    def watch_profiles_total(self, value: int) -> None:
        self._upd_stat("stat-profiles", "profiles", value)

    def watch_clusters_total(self, value: int) -> None:
        self._upd_stat("stat-clusters", "clusters", value)

    def watch_leaks_total(self, value: int) -> None:
        self._upd_stat("stat-leaks", "leaks", value)

    def run_search(
        self,
        username: str,
        include_migrated: bool = False,
        no_cache: bool = False,
        sync_mode: bool = False,
        lang: str = "zh",
    ) -> None:
        """Start a search in a background worker."""
        if self._searching:
            return  # ignore duplicate calls

        self.username = username
        self._searching = True
        self._cancel_event = asyncio.Event()
        self._search_lang = lang

        # Clear previous results
        for wid in ("hits-log", "profiles-log", "clusters-log", "leaks-log"):
            self.query_one(f"#{wid}", RichLog).clear()
        self.hits_total = 0
        self.profiles_total = 0
        self.clusters_total = 0
        self.leaks_total = 0

        self.query_one("#loading", LoadingIndicator).display = True
        self.query_one("#btn-cancel", Button).display = True
        self.status_text = f"🔍 Searching {username}..."

        self.run_worker(
            self._do_search(username, include_migrated, no_cache, sync_mode, lang),
            exclusive=True,
        )

    async def _do_search(
        self,
        username: str,
        include_migrated: bool,
        no_cache: bool,
        sync_mode: bool = False,
        lang: str = "zh",
    ) -> None:
        """Run the pipeline and display results."""
        t0 = time.monotonic()
        try:
            config = load_config()
            sites = load_all_sites(include_migrated=include_migrated)
            engines = load_engines()
            extractors = discover_extractors()

            cache = None if no_cache else ResultCache()

            self.status_text = f"🔍 Probing {len(sites)} sites..."
            pipeline = AsyncPipeline(
                sites=sites,
                engines=engines,
                extractors=extractors,
                config=config,
                cache=cache,
            )

            result = await pipeline.run(username)

            if self._cancel_event and self._cancel_event.is_set():
                self.status_text = "⏹ Cancelled"
                return

            elapsed = time.monotonic() - t0
            self._last_result = result
            self._display_results(result, username, elapsed)
            self.status_text = (
                f"✅ Done in {elapsed:.1f}s — "
                f"{len(result.hits)} hits · "
                f"{len(result.profiles)} profiles · "
                f"{len(result.clusters)} clusters"
            )
        except Exception as e:
            self.status_text = f"❌ Error: {e}"
            self.query_one("#hits-log", RichLog).write(
                f"[red]Search failed: {e}[/red]"
            )
        finally:
            self._searching = False
            self.query_one("#loading", LoadingIndicator).display = False
            self.query_one("#btn-cancel", Button).display = False

    def _display_results(self, result, username: str, elapsed: float) -> None:
        """Render search results into the panels."""
        self.hits_total = len(result.hits)
        self.profiles_total = len(result.profiles)
        self.clusters_total = len(result.clusters)
        self.leaks_total = len(result.leak_records)

        hits_log = self.query_one("#hits-log", RichLog)
        for hit in result.hits:
            site_id = hit.get("site_id", hit.get("id", "?"))
            status = hit.get("status", "?")
            url = hit.get("url", "")
            conf = hit.get("confidence", 0.5)
            color = _color_for_confidence(conf)
            hits_log.write(
                f"[{color}]●[/{color}] [bold]{site_id}[/bold] "
                f"({status}) [dim]{url}[/dim]"
            )
        if not result.hits:
            hits_log.write("[dim]No hits found[/dim]")

        profiles_log = self.query_one("#profiles-log", RichLog)
        for p in result.profiles:
            name = p.get("display_name") or p.get("username", "?")
            site = p.get("site_id", "?")
            loc = p.get("location", "")
            loc_str = f" 📍 {loc}" if loc else ""
            profiles_log.write(
                f"  [bold]{name}[/bold] [dim]@{site}{loc_str}[/dim]"
            )
        if not result.profiles:
            profiles_log.write("[dim]No profiles extracted[/dim]")

        clusters_log = self.query_one("#clusters-log", RichLog)
        for i, c in enumerate(result.clusters):
            sites_in = getattr(c, "site_ids", [])
            conf_val = getattr(c, "confidence", 0.0)
            clusters_log.write(
                f"\n  Cluster {i+1}: "
                f"[bold]{', '.join(sites_in[:5])}[/bold]"
                f"{'…' if len(sites_in) > 5 else ''}"
                f" [dim]confidence={conf_val}[/dim]"
            )
            evidence = getattr(c, "evidence", [])
            for ev in evidence[:3]:
                clusters_log.write(f"    └ {ev}")
        if not result.clusters:
            clusters_log.write("[dim]No identity clusters formed[/dim]")

        leaks_log = self.query_one("#leaks-log", RichLog)
        for r in result.leak_records:
            email = getattr(r, "email", "?") or "?"
            domain = getattr(r, "domain", "")
            src = getattr(r, "source", "?")
            breaches = getattr(r, "breach_date", "")
            breaches_str = f" ({breaches})" if breaches else ""
            leaks_log.write(
                f"  [bold]{email}[/bold]"
                f"{f' @{domain}' if domain else ''}"
                f" [dim]{src}{breaches_str}[/dim]"
            )
        if not result.leak_records:
            leaks_log.write("[dim]No leak records found[/dim]")

    def _export_report(self, fmt: str) -> None:
        """Generate and save a report file."""
        if self._last_result is None:
            self.status_text = "❌ No results to export"
            return

        path = Path(f"clawithme_report_{self.username}.{fmt}")
        try:
            from clawithme.report.generator import generate_report  # noqa: PLC0415

            html = generate_report(
                hits=self._last_result.hits,
                profiles=self._last_result.profiles,
                clusters=self._last_result.clusters,
                username=self.username,
                breach_dates=self._last_result.leak_records,
                lang=self._search_lang,
            )

            if fmt == "html":
                path.write_text(html, encoding="utf-8")
            elif fmt == "json":
                path.write_text(
                    json.dumps(
                        {
                            "username": self.username,
                            "hits": self._last_result.hits,
                            "profiles": self._last_result.profiles,
                            "clusters": [
                                {
                                    "site_ids": list(getattr(c, "site_ids", [])),
                                    "confidence": getattr(c, "confidence", 0),
                                    "evidence": list(
                                        getattr(c, "evidence", [])
                                    ),
                                }
                                for c in self._last_result.clusters
                            ],
                            "leaks": [
                                {
                                    "email": getattr(r, "email", ""),
                                    "domain": getattr(r, "domain", ""),
                                    "source": getattr(r, "source", ""),
                                }
                                for r in self._last_result.leak_records
                            ],
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )
            elif fmt == "md":
                from clawithme.report.generator import export_markdown  # noqa: PLC0415

                md = export_markdown(
                    hits=self._last_result.hits,
                    profiles=self._last_result.profiles,
                    clusters=self._last_result.clusters,
                    username=self.username,
                    breach_dates=self._last_result.leak_records,
                )
                path.write_text(md, encoding="utf-8")

            self.status_text = f"📄 Saved {path.name}"
        except Exception as e:
            self.status_text = f"❌ Export failed: {e}"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle action bar buttons."""
        btn = event.button.id
        if btn == "btn-new":
            self._searching = False
            self.app.pop_screen()
        elif btn == "btn-cancel":
            if self._cancel_event:
                self._cancel_event.set()
            self.status_text = "⏹ Cancelling..."
        elif btn == "btn-html":
            self._export_report("html")
        elif btn == "btn-json":
            self._export_report("json")
        elif btn == "btn-md":
            self._export_report("md")
