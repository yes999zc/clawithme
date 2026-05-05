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

from clawithme.cache import ResultCache
from clawithme.config import load_config
from clawithme.crawler.base import Profile
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import get_engine_for_site, load_engines
from clawithme.leak_sources import CavalierSource
from clawithme.leak_sources.hibp import HIBPSource
from clawithme.leak_sources.manager import query_breaches
from clawithme.logging import get_logger, new_trace_id, setup_logging
from clawithme.signals.correlation import CorrelationEngine
from clawithme.signals.llm_verifier import LLMVerifier

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

def _search_leaks(search_term: str, search_type: str,
                  report_path: str | None, report_format: str,
                  acknowledged: bool, cache: ResultCache | None = None):
    """Email or phone search: leak database only (no site probing).

    search_type: "email" or "phone"
    """
    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, search_term=search_term, search_type=search_type)
    cfg = load_config()

    log.info("search_start", search_type=search_type)

    # Phase 3: Leak database
    async def query_leaks():
        sources: list = [CavalierSource()]
        if cfg.apis.hibp_api_key:
            sources.append(HIBPSource(api_key=cfg.apis.hibp_api_key))
        kwargs = {search_type: search_term}
        records = await query_breaches(sources, **kwargs)
        # Follow-up: cross-search with the other identifier
        if search_type == "email":
            phones = [r.phone for r in records if r.phone]
            if phones:
                phone_records = await query_breaches(sources, phone=phones[0])
                records.extend(phone_records)
        else:  # phone
            emails = [r.email for r in records if r.email]
            if emails:
                email_records = await query_breaches(sources, email=emails[0])
                records.extend(email_records)
        for src in sources:
            await src.close()
        return records

    try:
        leak_records = asyncio.run(query_leaks())
    except (OSError, ValueError, TimeoutError, RuntimeError) as e:
        log.warning("leak_query_failed", error=str(e))
        leak_records = []

    # Phase 4: Correlation
    profile_objects: list[Profile] = []
    for r in leak_records:
        profile_objects.append(Profile(
            site_id=f"leak:{r.source or 'unknown'}",
            site_name=r.source or "Leak DB",
            url="",
            username=r.username or search_term,
            email=r.email,
            phone=r.phone,
        ))
    engine = CorrelationEngine()
    clusters = engine.correlate(profile_objects)

    # Output
    print()
    label = {"email": "email", "phone": "phone"}[search_type]
    print(f"═══ clawithme search ({label}): {search_term} ═══")
    print()

    sources_used = ["Cavalier"]
    if cfg.apis.hibp_api_key:
        sources_used.append("HIBP")
    if leak_records:
        print(f"🔓 Leak records: {len(leak_records)} (sources: {', '.join(sources_used)})")
        for r in leak_records:
            print(f"   ⚠️  {r}")
        leak_domains: set[str] = {r.domain for r in leak_records if r.domain}
        if leak_domains:
            print(f"📧 Breach-associated platforms: {', '.join(sorted(leak_domains))}")
        leak_phones: set[str] = {r.phone for r in leak_records if r.phone}
        if leak_phones:
            print(f"📱 Phone numbers revealed: {', '.join(sorted(leak_phones))}")
        leak_emails: set[str] = {r.email for r in leak_records if r.email}
        if leak_emails:
            print(f"📧 Emails revealed: {', '.join(sorted(leak_emails))}")
    else:
        print(f"🔓 Leak records: 0 (sources: {', '.join(sources_used)})")

    if len(clusters) > 0:
        print()
        multi = sum(1 for c in clusters if len(c.profiles) > 1)
        print(f"🔗 Identity clusters: {len(clusters)} total, {multi} multi-profile")
        for i, c in enumerate(clusters, 1):
            if len(c.profiles) == 1:
                continue
            sites = [p.site_id for p in c.profiles]
            print(f"   Cluster {i}: {', '.join(sites)}")
            print(f"      confidence={c.confidence}  signals={c.signals}")

    print()
    log.info("search_done", leaks=len(leak_records))
    print(f"trace_id: {trace_id}")

    # Report
    if report_path:
        breach_dates = [r.breach_date for r in leak_records if r.breach_date]
        if report_format == "json":
            from clawithme.report.generator import export_json
            output = export_json([], [], clusters, search_term, trace_id=trace_id)
        else:
            from clawithme.report.generator import generate_report
            output = generate_report([], [], clusters, search_term,
                                     trace_id=trace_id, breach_dates=breach_dates)
        try:
            safe_path = Path(report_path).resolve()
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




def search(username: str, *, report_path: str | None = None, report_format: str = "html",
           include_migrated: bool = False, acknowledged: bool = False,
           no_cache: bool = False):
    """Run a full search: site probes → profile extraction → leak database.

    If report_path is given, write an HTML panorama report to that path.
    If include_migrated, also search maigret-migrated sites (~2500).
    Requires --acknowledge-ethical-use flag to confirm responsible use.
    """
    # Detect search type: email, phone, or username
    if "@" in username:
        search_type = "email"
    elif re.match(r"^\d{7,15}$", username):
        search_type = "phone"
    else:
        search_type = "username"

    # Validate input format
    if search_type == "username" and not _USERNAME_RE.match(username):
        log = get_logger()
        log.error("invalid_username", username=username)
        print(f"❌ Invalid username: {username!r} (allowed: letters, digits, . _ -)")
        return

    if not acknowledged:
        print("🛡️  ETHICAL USE REQUIRED")
        print()
        print("   This tool queries public profiles and breach databases.")
        print("   Use only on accounts you own or have explicit authorization.")
        print("   Unauthorized use violates platform ToS, privacy laws, and ethical norms.")
        print()
        print("   Re-run with: clawithme search <username> --acknowledge-ethical-use")
        return

    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)

    # ── Load config ──
    cfg = load_config()

    # ── Init cache (skip if --no-cache) ──
    cache: ResultCache | None = None
    if not no_cache:
        try:
            cache = ResultCache()
        except OSError as e:
            log.warning("cache_init_failed", error=str(e))

    # ── Init LLM verifier (if API key available) ──
    llm_verifier: LLMVerifier | None = None
    if LLMVerifier.is_configured():
        llm_verifier = LLMVerifier()

    # Email/phone search: leak DB only, no site probing
    if search_type != "username":
        return _search_leaks(username, search_type, report_path, report_format, acknowledged)

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

        site_id = site["id"]
        cache_key = f"probe:{username}:{site_id}"

        # Check cache first
        cached = None
        if cache is not None:
            cached = cache.get(cache_key)

        if cached is not None:
            if cached.get("exists"):
                hits.append(cached["hit"])
                log.info("hit_cache", site=cached["hit"]["site_name"])
            continue

        try:
            result = engine.probe(site, username)
        except ValueError as e:
            log.warning("probe_template_error", site_id=site_id, error=str(e))
            continue

        if result.exists:
            hit = {
                "site_id": result.site_id,
                "site_name": result.site_name,
                "url": result.url_probed,
                "status": result.status_code,
                "site_def": site,
            }
            hits.append(hit)
            log.info("hit", site=result.site_name, status=result.status_code)
            if cache is not None:
                cache.set(cache_key, {"exists": True, "hit": hit})
        elif cache is not None:
            cache.set(cache_key, {"exists": False})

    # ── Phase 1.5: SearXNG fallback for un-hit sites ──
    searxng_total = 0
    try:
        import urllib.parse
        import urllib.request
        hit_ids = {h["site_id"] for h in hits}
        searxng_base = "http://localhost:8888/search"
        for site in sites[:50]:  # cap: only top 50 un-hit sites
            sid = site["id"]
            if sid in hit_ids:
                continue
            domain = site.get("domain") or site.get("urlMain", "")
            if not domain:
                continue
            # Extract bare domain from urlMain if needed
            if "://" in domain:
                domain = domain.split("://")[-1].split("/")[0]
            query = f'site:{domain} "{username}"'
            url = f"{searxng_base}?q={urllib.parse.quote(query)}&format=json"
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    data = json.loads(resp.read())
                    results = data.get("results", [])
                    if results:
                        hits.append({
                            "site_id": sid,
                            "site_name": site.get("name", sid),
                            "url": results[0].get("url", ""),
                            "status": 0,  # SearXNG result, not HTTP probe
                            "site_def": site,
                        })
                        searxng_total += 1
            except (OSError, ValueError, TimeoutError):
                continue
    except (OSError, ValueError, TimeoutError, json.JSONDecodeError):
        pass  # SearXNG unavailable — skip gracefully

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
                    "username": profile.username,
                    "display_name": profile.display_name,
                    "bio": profile.bio,
                    "location": profile.location,
                    "avatar_url": profile.avatar_url,
                    "email": profile.email,
                    "phone": profile.phone,
                    "joined_date": profile.joined_date,
                    "post_count": profile.post_count,
                    "follower_count": profile.follower_count,
                    "following_count": profile.following_count,
                    "extra": profile.extra,
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
        # Follow-up: query by email if username search returned emails
        emails_found = [r.email for r in records if r.email]
        if emails_found:
            email_records = await query_breaches(sources, email=emails_found[0])
            records.extend(email_records)
        # Follow-up: query by phone if username search returned phone numbers
        phones_found = [r.phone for r in records if r.phone]
        if phones_found:
            phone_records = await query_breaches(sources, phone=phones_found[0])
            records.extend(phone_records)
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

    engine = CorrelationEngine(llm_verifier=llm_verifier)
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
            if p["follower_count"] is not None:
                parts.append(f"👥 {p['follower_count']}")
            print(" ".join(parts))

    print()
    sources_used = ["Cavalier"]
    if cfg.apis.hibp_api_key:
        sources_used.append("HIBP")
    if leak_records:
        print(f"🔓 Leak records: {len(leak_records)} (sources: {', '.join(sources_used)})")
        for r in leak_records:
            print(f"   ⚠️  {r}")
        # Extract associated platforms from breach domains
        leak_domains: set[str] = {r.domain for r in leak_records if r.domain}
        if leak_domains:
            print(f"📧 Breach-associated platforms: {', '.join(sorted(leak_domains))}")
        # Extract phone numbers found in breaches
        leak_phones: set[str] = {r.phone for r in leak_records if r.phone}
        if leak_phones:
            print(f"📱 Phone numbers revealed: {', '.join(sorted(leak_phones))}")
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
             leaks=len(leak_records), searxng_hits=searxng_total)
    print(f"trace_id: {trace_id}")

    # ── Report (optional) ──
    if report_path:
        breach_dates = [r.breach_date for r in leak_records if r.breach_date]
        if report_format == "json":
            from clawithme.report.generator import export_json
            output = export_json(hits, profiles, clusters, username, trace_id=trace_id)
        else:
            from clawithme.report.generator import generate_report
            output = generate_report(hits, profiles, clusters, username,
                                     trace_id=trace_id, breach_dates=breach_dates)
        try:
            safe_path = Path(report_path).resolve()
            # Check resolved path for traversal
            if ".." in str(safe_path):
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
        print("Usage: clawithme search <username> [--report <path>] "
              "[--format html|json] [--include-migrated] [--no-cache] "
              "[--acknowledge-ethical-use]")
        print("       clawithme verify")
        print("       clawithme validate")
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: clawithme search <username> [--report <path>] "
                  "[--format html|json] [--include-migrated] [--no-cache] "
                  "[--acknowledge-ethical-use]")
            sys.exit(1)
        username = sys.argv[2]
        report_path = None
        report_format = "html"
        include_migrated = "--include-migrated" in sys.argv
        no_cache = "--no-cache" in sys.argv
        acknowledged = "--acknowledge-ethical-use" in sys.argv
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
               include_migrated=include_migrated, acknowledged=acknowledged,
               no_cache=no_cache)

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
