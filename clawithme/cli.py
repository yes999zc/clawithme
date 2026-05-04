"""CLI entry point for clawithme.

Usage:
    clawithme search <username>     Search across all sites + leak sources
    clawithme verify                Verify site detection rules
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import get_engine_for_site, load_engines
from clawithme.leak_sources import CavalierSource
from clawithme.logging import get_logger, new_trace_id, setup_logging

logger = get_logger()


def load_all_sites() -> list[dict]:
    """Load all non-deprecated site definitions."""
    sites_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
    sites: list[dict] = []
    for json_file in sorted(sites_dir.rglob("*.json")):
        if "migrated" in json_file.parts:
            continue
        site = json.loads(json_file.read_text())
        if not site.get("deprecated", False):
            sites.append(site)
    return sites


def search(username: str):
    """Run a full search: site probes → profile extraction → leak database."""
    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)

    # ── Phase 1: Site probing (engine) ──
    sites = load_all_sites()
    engines = load_engines()
    extractors = discover_extractors()

    log.info("search_start", sites=len(sites), engines=len(engines),
             extractors=len(extractors))

    hits: list[dict] = []
    for site in sites:
        engine = get_engine_for_site(site, engines)
        if engine is None:
            log.warning("engine_missing", site_id=site["id"])
            continue

        try:
            result = engine.probe(site, username)
        except ValueError as e:
            log.warning("probe_template_error", site_id=site["id"], error=str(e))
            continue

        if result.exists:
            hits.append({
                "site_id": result.site_id,
                "site_name": result.site_name,
                "url": result.url_probed,
                "status": result.status_code,
                "site_def": site,  # pass site definition to extractor
            })
            log.info("hit", site=result.site_name, status=result.status_code)

    # ── Phase 2: Profile extraction (crawler) ──
    profiles: list[dict] = []
    for hit in hits:
        site_id = hit["site_id"]
        extractor_cls = extractors.get(site_id)
        if extractor_cls is None:
            continue

        try:
            extractor = extractor_cls()
            profile = extractor.extract(hit["site_def"], username)
            if not profile.empty:
                profiles.append({
                    "site_id": profile.site_id,
                    "display_name": profile.display_name,
                    "bio": profile.bio,
                    "location": profile.location,
                    "avatar_url": profile.avatar_url,
                    "followers": profile.follower_count,
                    "empty": False,
                })
                log.debug("profile_extracted", site=site_id,
                         display_name=profile.display_name)
        except (OSError, ValueError, TimeoutError) as e:
            log.warning("extract_failed", site=site_id, error=str(e))

    # ── Phase 3: Leak database ──
    async def query_leaks():
        src = CavalierSource()
        records = await src.search_by_username(username)
        await src.close()
        return records

    try:
        leak_records = asyncio.run(query_leaks())
    except (OSError, ValueError, TimeoutError, RuntimeError) as e:
        log.warning("leak_query_failed", error=str(e))
        leak_records = []

    # ── Output ──
    print()
    print(f"═══ clawithme search: {username} ═══")
    print()

    if hits:
        print(f"📊 Sites found: {len(hits)}/{len(sites)}")
        for h in hits:
            print(f"   ✅ {h['site_name']:12s} → {h['url']}")
    else:
        print(f"📊 Sites found: 0/{len(sites)}")

    if profiles:
        print()
        print(f"👤 Profiles extracted: {len(profiles)}")
        for p in profiles:
            parts = [f"   {p['site_id']}"]
            if p["display_name"]:
                parts.append(f"→ {p['display_name']}")
            if p["location"]:
                parts.append(f"📍 {p['location']}")
            if p["followers"] is not None:
                parts.append(f"👥 {p['followers']}")
            print(" ".join(parts))

    print()
    if leak_records:
        print(f"🔓 Leak records: {len(leak_records)}")
        for r in leak_records:
            print(f"   ⚠️  {r}")
    else:
        print("🔓 Leak records: 0 (no known breaches)")

    print()
    log.info("search_done", hits=len(hits), profiles=len(profiles),
             leaks=len(leak_records))
    print(f"trace_id: {trace_id}")


def main():
    """CLI entry point."""
    setup_logging()

    if len(sys.argv) < 2:
        print("Usage: clawithme search <username>")
        print("       clawithme verify")
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: clawithme search <username>")
            sys.exit(1)
        username = sys.argv[2]
        search(username)

    elif command == "verify":
        # Delegate to verify_site.py
        import subprocess
        script = Path(__file__).resolve().parent.parent / "scripts" / "verify_site.py"
        args = [sys.executable, str(script), "--all"]
        if len(sys.argv) > 2:
            args = [sys.executable, str(script), sys.argv[2]]
        subprocess.run(args, check=False)  # verify script exits non-zero on failures

    else:
        print(f"Unknown command: {command}")
        print("Usage: clawithme search <username>")
        sys.exit(1)


if __name__ == "__main__":
    main()
