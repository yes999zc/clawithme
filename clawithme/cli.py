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

from clawithme.engine.loader import load_engines, get_engine_for_site
from clawithme.leak_sources import CavalierSource
from clawithme.logging import setup_logging, new_trace_id, get_logger

logger = get_logger()


def load_all_sites() -> list[dict]:
    """Load all non-deprecated site definitions."""
    sites_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
    sites: list[dict] = []
    for json_file in sorted(sites_dir.rglob("*.json")):
        site = json.loads(json_file.read_text())
        if not site.get("deprecated", False):
            sites.append(site)
    return sites


def search(username: str):
    """Run a full search: site probes + leak database query."""
    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)

    # ── Site probing ──
    sites = load_all_sites()
    engines = load_engines()

    log.info("search_start", sites=len(sites), engines=len(engines))

    hits: list[dict] = []
    for site in sites:
        engine = get_engine_for_site(site, engines)
        if engine is None:
            log.warning("engine_missing", site_id=site["id"])
            continue

        result = engine.probe(site, username)
        if result.exists:
            hits.append({
                "site_id": result.site_id,
                "site_name": result.site_name,
                "url": result.url_probed,
                "status": result.status_code,
            })
            log.info("hit", site=result.site_name, status=result.status_code)

    # ── Leak database ──
    async def query_leaks():
        src = CavalierSource()
        records = await src.search_by_username(username)
        await src.close()
        return records

    try:
        leak_records = asyncio.run(query_leaks())
    except Exception as e:
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

    print()
    if leak_records:
        print(f"🔓 Leak records: {len(leak_records)}")
        for r in leak_records:
            print(f"   ⚠️  {r}")
    else:
        print("🔓 Leak records: 0 (no known breaches)")

    print()
    log.info("search_done", hits=len(hits), leaks=len(leak_records))
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
        subprocess.run(args)

    else:
        print(f"Unknown command: {command}")
        print("Usage: clawithme search <username>")
        sys.exit(1)


if __name__ == "__main__":
    main()
