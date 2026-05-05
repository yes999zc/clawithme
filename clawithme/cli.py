"""CLI entry point for clawithme.

Usage:
    clawithme search <username>     Search across all sites + leak sources
    clawithme verify                Verify site detection rules
    clawithme validate              Validate site JSONs against schema
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

from clawithme.config import load_config
from clawithme.crawler.base import Profile
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import get_engine_for_site, load_engines
from clawithme.leak_sources import CavalierSource
from clawithme.leak_sources.hibp import HIBPSource
from clawithme.leak_sources.manager import query_breaches
from clawithme.logging import get_logger, new_trace_id, setup_logging
from clawithme.signals.correlation import CorrelationEngine

logger = get_logger()

# Most platforms allow letters, digits, dots, underscores, hyphens in usernames.
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def load_all_sites(validate: bool = False, include_migrated: bool = False) -> list[dict]:
    """Load all non-deprecated site definitions.

    If validate=True, checks each site against data/schema.json.
    Validation failures are logged but do not block loading.
    If include_migrated=True, also loads sites from migrated/ directory.
    """
    sites_dir = Path(__file__).resolve().parent.parent / "data" / "sites"
    schema_path = sites_dir.parent / "schema.json"
    sites: list[dict] = []

    schema = None
    if validate and schema_path.exists():
        import jsonschema
        schema = json.loads(schema_path.read_text())

    for json_file in sorted(sites_dir.rglob("*.json")):
        if not include_migrated and "migrated" in json_file.parts:
            continue
        site = json.loads(json_file.read_text())
        if site.get("deprecated", False):
            continue
        if schema:
            try:
                jsonschema.validate(instance=site, schema=schema)
            except jsonschema.ValidationError as e:
                logger.warning("schema_validation_failed",
                               site_id=site.get("id", json_file.name),
                               error=str(e))
        sites.append(site)
    return sites


def search(username: str, *, report_path: str | None = None, report_format: str = "html",
           include_migrated: bool = False):
    """Run a full search: site probes → profile extraction → leak database.

    If report_path is given, write an HTML panorama report to that path.
    If include_migrated, also search maigret-migrated sites (~2500).
    """
    # Validate username against common pattern
    if not _USERNAME_RE.match(username):
        log = get_logger()
        log.error("invalid_username", username=username)
        print(f"❌ Invalid username: {username!r} (allowed: letters, digits, . _ -)")
        return

    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)

    # ── Load config ──
    cfg = load_config()

    # ── Phase 1: Site probing (engine) ──
    try:
        sites = load_all_sites(include_migrated=include_migrated)
    except (OSError, json.JSONDecodeError) as e:
        log.error("site_load_failed", error=str(e))
        print(f"❌ Failed to load site definitions: {e}")
        return
    try:
        engines = load_engines()
    except (OSError, json.JSONDecodeError) as e:
        log.error("engine_load_failed", error=str(e))
        print(f"❌ Failed to load engine definitions: {e}")
        return
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
    profile_objects: list[Profile] = []  # kept for Phase 4 correlation
    for hit in hits:
        site_id = hit["site_id"]
        extractor_cls = extractors.get(site_id)
        if extractor_cls is None:
            continue

        try:
            extractor = extractor_cls()
            profile = extractor.extract(hit["site_def"], username)
            profile_objects.append(profile)
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
        sources: list = [CavalierSource()]
        if cfg.apis.hibp_api_key:
            sources.append(HIBPSource(api_key=cfg.apis.hibp_api_key))
        records = await query_breaches(sources, username=username)
        for src in sources:
            await src.close()
        return records

    try:
        leak_records = asyncio.run(query_leaks())
    except (OSError, ValueError, TimeoutError, RuntimeError) as e:
        log.warning("leak_query_failed", error=str(e))
        leak_records = []

    # ── Phase 4: Correlation ──
    for r in leak_records:
        profile_objects.append(Profile(
            site_id=f"leak:{r.source or 'unknown'}",
            site_name=r.source or "Leak DB",
            url="",
            username=r.username or username,
            email=r.email,
            phone=r.phone,
        ))

    engine = CorrelationEngine()
    clusters = engine.correlate(profile_objects)

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
    sources_used = ["Cavalier"]
    if cfg.apis.hibp_api_key:
        sources_used.append("HIBP")
    if leak_records:
        print(f"🔓 Leak records: {len(leak_records)} (sources: {', '.join(sources_used)})")
        for r in leak_records:
            print(f"   ⚠️  {r}")
    else:
        print(f"🔓 Leak records: 0 (sources: {', '.join(sources_used)})")

    if len(clusters) > 0:
        print()
        multi = sum(1 for c in clusters if len(c.profiles) > 1)
        print(f"🔗 Identity clusters: {len(clusters)} total, {multi} multi-profile")
        for i, c in enumerate(clusters, 1):
            if len(c.profiles) == 1:
                continue  # skip singletons for cleaner output
            sites = [p.site_id.replace("leak:", "🔓") for p in c.profiles]
            print(f"   Cluster {i}: {', '.join(sites)}")
            print(f"      confidence={c.confidence}  signals={c.signals}")

    print()
    log.info("search_done", hits=len(hits), profiles=len(profiles),
             leaks=len(leak_records))
    print(f"trace_id: {trace_id}")

    # ── Report (optional) ──
    if report_path:
        if report_format == "json":
            from clawithme.report.generator import export_json
            output = export_json(hits, profiles, clusters, username, trace_id=trace_id)
        else:
            from clawithme.report.generator import generate_report
            output = generate_report(hits, profiles, clusters, username, trace_id=trace_id)
        try:
            safe_path = Path(report_path).resolve()
            # Only block paths that escape cwd — allow /tmp and subdirs
            if ".." in str(Path(report_path)):
                log.error("report_path_traversal", path=report_path)
                print("\n❌ Report path must not contain '..'")
                return
            safe_path.write_text(output)
            log.info("report_written", path=report_path, format=report_format)
            print(f"\n📄 Report ({report_format}): {report_path}")
        except OSError as e:
            log.error("report_write_failed", path=report_path, error=str(e))
            print(f"\n❌ Failed to write report: {e}")


def main():
    """CLI entry point."""
    setup_logging()

    if len(sys.argv) < 2:
        print("Usage: clawithme search <username> [--report <path>] [--include-migrated]")
        print("       clawithme verify")
        print("       clawithme validate")
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: clawithme search <username> [--report <path>] [--include-migrated]")
            sys.exit(1)
        username = sys.argv[2]
        report_path = None
        report_format = "html"
        include_migrated = "--include-migrated" in sys.argv
        if "--report" in sys.argv:
            idx = sys.argv.index("--report")
            if idx + 1 < len(sys.argv):
                report_path = sys.argv[idx + 1]
        if "--format" in sys.argv:
            idx = sys.argv.index("--format")
            if idx + 1 < len(sys.argv):
                report_format = sys.argv[idx + 1]
        if report_format not in ("html", "json"):
            print(f"❌ Unknown format: {report_format!r}. Use 'html' or 'json'.")
            sys.exit(1)
        search(username, report_path=report_path, report_format=report_format,
               include_migrated=include_migrated)

    elif command == "verify":
        # Delegate to verify_site.py
        import subprocess
        script = Path(__file__).resolve().parent.parent / "scripts" / "verify_site.py"
        args = [sys.executable, str(script), "--all"]
        if len(sys.argv) > 2:
            args = [sys.executable, str(script), sys.argv[2]]
        subprocess.run(args, check=False)  # verify script exits non-zero on failures

    elif command == "validate":
        print("Validating site definitions against schema...")
        sites = load_all_sites(validate=True)
        print(f"  Loaded {len(sites)} sites with schema validation (warnings above)")

    else:
        print(f"Unknown command: {command}")
        print("Usage: clawithme search <username>")
        print("       clawithme verify")
        print("       clawithme validate")
        sys.exit(1)


if __name__ == "__main__":
    main()
