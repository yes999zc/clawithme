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
import sqlite3
import sys
from pathlib import Path

from clawithme.cache import ResultCache
from clawithme.config import load_config
from clawithme.crawler.base import Profile
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import get_engine_for_site, load_engines
from clawithme.engine.proxy_manager import ProxyManager
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

    # Phase 3: Leak database (shared helper)
    kwargs = {}
    if search_type == "email":
        kwargs["email"] = search_term
    else:
        kwargs["phone"] = search_term
    leak_records = _query_all_leaks(cfg, **kwargs)

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
    clusters = CorrelationEngine().correlate(profile_objects)

    sources_used = ["Cavalier"]
    if cfg.apis.hibp_api_key:
        sources_used.append("HIBP")

    # Output
    _print_search_results(
        search_term, search_type, hits=[], profiles=[], leak_records=leak_records,
        clusters=clusters, searxng_hits=None, sources_used=sources_used,
        trace_id=trace_id,
    )

    log.info("search_done", leaks=len(leak_records))

    # Report
    if report_path:
        breach_dates = [r.breach_date for r in leak_records if r.breach_date]
        _write_search_report(
            report_path, report_format, hits=[], profiles=[], clusters=clusters,
            username=search_term, trace_id=trace_id, breach_dates=breach_dates,
            log=log, lang="zh", leak_records=leak_records,
        )




def _write_report(output: str | bytes, path_str: str, fmt: str,
                  log, *, mode: str = "text") -> None:
    """Write a report file with path traversal protection.

    mode='text' → write_text, mode='bytes' → write_bytes (for PDF).
    """
    try:
        safe_path = Path(path_str).resolve()
        cwd = Path.cwd().resolve()
        try:
            safe_path.relative_to(cwd)
        except ValueError:
            log.error("report_path_traversal", path=path_str)
            print("\n❌ Report path must be within current directory")
            return
        if mode == "bytes":
            safe_path.write_bytes(output)  # type: ignore[arg-type]
        else:
            safe_path.write_text(output)  # type: ignore[arg-type]
        log.info("report_written", path=path_str, format=fmt)
        print(f"\n📄 Report ({fmt}): {path_str}")
    except OSError as e:
        log.error("report_write_failed", path=path_str, error=str(e))
        print(f"\n❌ Failed to write report: {e}")


def search(username: str, *, report_path: str | None = None, report_format: str = "html",
           include_migrated: bool = False, acknowledged: bool = False,
           no_cache: bool = False, incremental: bool = False,
           async_mode: bool = True, lang: str = "zh"):
    """Run a full search: site probes → profile extraction → leak database.

    If report_path is given, write an HTML panorama report to that path.
    If include_migrated, also search maigret-migrated sites (~2500).
    Requires --acknowledge-ethical-use flag to confirm responsible use.
    If async_mode=False, uses legacy serial pipeline (slower, debug-friendly).
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

    # Async pipeline path (default)
    if async_mode and search_type == "username":
        try:
            return _search_async(
                username, report_path=report_path, report_format=report_format,
                include_migrated=include_migrated, no_cache=no_cache,
                incremental=incremental, lang=lang,
            )
        except RuntimeError:
            # Nested event loop (e.g., pytest-asyncio) — fall back to sync
            pass

    # Legacy serial pipeline (sync fallback for email/phone/debug)
    return _search_sync(
        username, search_type=search_type, report_path=report_path,
        report_format=report_format, include_migrated=include_migrated,
        no_cache=no_cache, incremental=incremental, acknowledged=acknowledged,
    )


def _search_async(username: str, *, report_path: str | None = None,
                  report_format: str = "html", include_migrated: bool = False,
                  no_cache: bool = False, incremental: bool = False,
                  lang: str = "zh"):
    """Async pipeline: parallel probes + extraction (6-38x faster).

    If *incremental* is True, stale cache entries are reused regardless
    of TTL, and only sites with no cache entry are probed.
    """
    import asyncio

    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)
    cfg = load_config()

    # Init cache
    cache: ResultCache | None = None
    if not no_cache or incremental:
        try:
            cache = ResultCache()
        except (OSError, sqlite3.OperationalError) as e:
            log.warning("cache_init_failed", error=str(e))

    # Init LLM verifier
    llm_verifier: LLMVerifier | None = None
    llm = LLMVerifier()
    if llm.is_configured():
        llm_verifier = llm

    # Load sites, engines, extractors
    try:
        sites = load_all_sites(include_migrated=include_migrated)
    except (OSError, json.JSONDecodeError) as e:
        log.error("site_load_failed", error=str(e))
        print(f"❌ Failed to load site definitions: {e}")
        return
    try:
        engines = load_engines(proxy_manager=ProxyManager(cfg))
    except (OSError, json.JSONDecodeError) as e:
        log.error("engine_load_failed", error=str(e))
        print(f"❌ Failed to load engine definitions: {e}")
        return
    extractors = discover_extractors()

    log.info("search_start", sites=len(sites), engines=len(engines),
             extractors=len(extractors), mode="async")

    # Run pipeline
    from clawithme.pipeline import AsyncPipeline
    pipeline = AsyncPipeline(
        sites, engines, extractors, cfg,
        cache=cache, llm_verifier=llm_verifier,
        incremental=incremental,
    )

    try:
        result = asyncio.run(pipeline.run(username))
    except (OSError, ValueError, TimeoutError, RuntimeError) as e:
        log.error("pipeline_failed", error=str(e))
        print(f"❌ Search failed: {e}")
        return

    # Output
    sources_used = ["Cavalier"]
    if cfg.apis.hibp_api_key:
        sources_used.append("HIBP")
    _print_search_results(
        username, search_type="username", hits=result.hits, profiles=result.profiles,
        leak_records=result.leak_records, clusters=result.clusters,
        searxng_hits=result.searxng_hits, sources_used=sources_used,
        trace_id=trace_id, sites_total=len(sites),
    )

    log.info("search_done", hits=len(result.hits), profiles=len(result.profiles),
             leaks=len(result.leak_records), searxng_hits=result.searxng_hits)

    # Report
    if report_path:
        breach_dates = [r.breach_date for r in result.leak_records if r.breach_date]
        _write_search_report(
            report_path, report_format, hits=result.hits, profiles=result.profiles,
            clusters=result.clusters, username=username, trace_id=trace_id,
            breach_dates=breach_dates, log=log, lang=lang,
            leak_records=result.leak_records,
        )


def _search_sync(username: str, *, search_type: str, report_path: str | None,
                 report_format: str, include_migrated: bool,
                 no_cache: bool, incremental: bool, acknowledged: bool):
    """Legacy serial pipeline (backward compatible, debug-friendly)."""

    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)

    # ── Load config ──
    cfg = load_config()

    # ── Init cache (skip if --no-cache, but always init for --incremental) ──
    cache: ResultCache | None = None
    if not no_cache or incremental:
        try:
            cache = ResultCache()
        except (OSError, sqlite3.OperationalError) as e:
            log.warning("cache_init_failed", error=str(e))

    # ── Init LLM verifier (if API key available) ──
    llm_verifier: LLMVerifier | None = None
    llm = LLMVerifier()
    if llm.is_configured():
        llm_verifier = llm

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
        engines = load_engines(proxy_manager=ProxyManager(cfg))
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
            cached = cache.get(cache_key, ignore_expiry=incremental)

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
        elif not result.error and cache is not None:
            # Only cache legitimate negatives (user doesn't exist) with 1h TTL.
            # Probe failures (error != None) are skipped entirely.
            # Short TTL for negatives because anti-bot blocks (403) or rate
            # limits (429) are indistinguishable from true 404s at classifier level.
            cache.set(cache_key, {"exists": False}, ttl_seconds=3600)

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

    # ── Phase 3: Leak database (shared helper) ──
    leak_records = _query_all_leaks(cfg, username=username)

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

    sources_used = ["Cavalier"]
    if cfg.apis.hibp_api_key:
        sources_used.append("HIBP")

    # ── Output ──
    _print_search_results(
        username, search_type="username", hits=hits, profiles=profiles,
        leak_records=leak_records, clusters=clusters, searxng_hits=searxng_total,
        sources_used=sources_used, trace_id=trace_id, sites_total=len(sites),
    )

    log.info("search_done", hits=len(hits), profiles=len(profiles),
             leaks=len(leak_records), searxng_hits=searxng_total)

    # ── Report (optional) ──
    if report_path:
        breach_dates = [r.breach_date for r in leak_records if r.breach_date]
        _write_search_report(
            report_path, report_format, hits=hits, profiles=profiles,
            clusters=clusters, username=username, trace_id=trace_id,
            breach_dates=breach_dates, log=log, lang="zh",
            leak_records=leak_records,
        )


# ── Shared pipeline helpers (consolidated from _search_async / _search_sync / _search_leaks) ──


def _print_search_results(
    username: str,
    search_type: str,
    hits: list[dict],
    profiles: list[dict],
    leak_records: list,
    clusters: list,
    searxng_hits: int | None,
    sources_used: list[str],
    trace_id: str,
    sites_total: int = 0,
) -> None:
    """Print formatted search results to stdout.

    Called by _search_async, _search_sync, and _search_leaks.
    *sites_total* is the total number of sites probed (for the denominator).
    """
    print()
    if search_type in ("email", "phone"):
        label = {"email": "email", "phone": "phone"}[search_type]
        print(f"═══ clawithme search ({label}): {username} ═══")
    else:
        print(f"═══ clawithme search: {username} ═══")
    print()

    if search_type == "username":
        denom = f"/{sites_total}" if sites_total else ""
        if hits:
            print(f"📊 Sites found: {len(hits)}{denom}")
            for h in hits:
                print(f"   ✅ {h['site_name']:12s} → {h['url']}")
        else:
            print(f"📊 Sites found: 0{denom}")
        print()

        if profiles:
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

    if leak_records:
        print(f"🔓 Leak records: {len(leak_records)} (sources: {', '.join(sources_used)})")
        for r in leak_records:
            print(f"   ⚠️  {r}")
        leak_domains = {r.domain for r in leak_records if r.domain}
        if leak_domains:
            print(f"📧 Breach-associated platforms: {', '.join(sorted(leak_domains))}")
        leak_phones = {r.phone for r in leak_records if r.phone}
        if leak_phones:
            print(f"📱 Phone numbers revealed: {', '.join(sorted(leak_phones))}")
        leak_emails = {r.email for r in leak_records if r.email}
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
            site_ids = [p.site_id for p in c.profiles]
            print(f"   Cluster {i}: {', '.join(site_ids)}")
            print(f"      confidence={c.confidence}  signals={c.signals}")

    print()
    print(f"trace_id: {trace_id}")


def _write_search_report(
    report_path: str,
    report_format: str,
    hits: list[dict],
    profiles: list[dict],
    clusters: list,
    username: str,
    trace_id: str,
    breach_dates: list[str],
    log,
    lang: str = "zh",
    leak_records: list | None = None,
) -> None:
    """Write HTML/JSON/PDF report with path traversal protection.

    Called by _search_async, _search_sync, and _search_leaks.
    """
    if report_format == "json":
        from clawithme.report.generator import export_json
        output = export_json(hits, profiles, clusters, username, trace_id=trace_id)
        _write_report(output, report_path, report_format, log, mode="text")
    elif report_format == "pdf":
        from clawithme.report.generator import export_pdf
        output = export_pdf(hits, profiles, clusters, username,
                            trace_id=trace_id, breach_dates=breach_dates)
        _write_report(output, report_path, report_format, log, mode="bytes")
    elif report_format == "md":
        from clawithme.report.generator import export_markdown
        output = export_markdown(hits, profiles, clusters, username,
                                 trace_id=trace_id, breach_dates=breach_dates, lang=lang)
        _write_report(output, report_path, report_format, log, mode="text")
    else:
        from clawithme.report.generator import generate_report
        output = generate_report(hits, profiles, clusters, username,
                                 trace_id=trace_id, breach_dates=breach_dates,
                                 leak_records=leak_records, lang=lang)
        _write_report(output, report_path, report_format, log, mode="text")


def _query_all_leaks(
    cfg,
    *,
    username: str | None = None,
    email: str | None = None,
    phone: str | None = None,
) -> list:
    """Query all configured leak sources (Cavalier + optional HIBP).

    Performs follow-up cross-queries: if username search returns emails,
    also queries those emails; returns phones, also queries those phones.
    """
    async def _query():
        sources: list = [CavalierSource()]
        if cfg.apis.hibp_api_key:
            sources.append(HIBPSource(api_key=cfg.apis.hibp_api_key))
        kwargs = {}
        if username:
            kwargs["username"] = username
        if email:
            kwargs["email"] = email
        if phone:
            kwargs["phone"] = phone
        records = await query_breaches(sources, **kwargs)
        # Follow-up cross-queries
        if username or email:
            phones_found = [r.phone for r in records if r.phone]
            if phones_found:
                phone_records = await query_breaches(sources, phone=phones_found[0])
                records.extend(phone_records)
        if username or phone:
            emails_found = [r.email for r in records if r.email]
            if emails_found:
                email_records = await query_breaches(sources, email=emails_found[0])
                records.extend(email_records)
        for src in sources:
            await src.close()
        return records

    try:
        return asyncio.run(_query())
    except (OSError, ValueError, TimeoutError, RuntimeError) as e:
        logger = get_logger()
        logger.warning("leak_query_failed", error=str(e))
        return []


_BANNER = """╭────────────────────────────────── clawithme v0.1 · OSINT Identity Panorama ──────────────────────────────────╮
│                                                                                                                    │
│       █▀▀ █░░ ▄▀█ █░▄░█ ▀█▀ ▀█▀ █░█ █▄░▄█ █▀▀                         3000+ sites                           │
│       █▄▄ █▄▄ █▀█ █▀░▀█ ▄█▄ ░█░ █▀█ █░▀░█ ██▄                         49 profile extractors                  │
│                                                                           9 detection engines                    │
│     🔍 Username → Identity Panorama                                      4 report formats (html/json/pdf/md)    │
│                                                                                                                    │
│                                   3000+ sites · 49 extractors · 9 engines · 4 report types                          │
╰────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯"""


def main():
    """CLI entry point."""
    setup_logging()

    # ── Banner ────────────────────────────────────────────────
    if len(sys.argv) >= 2 and sys.argv[1] != "help":
        print()
        print(_BANNER)
        print()

    if len(sys.argv) < 2:
        print("Usage: clawithme search <username> [--report <path>] "
              "[--format html|json|pdf|md] [--include-migrated] [--no-cache] "
              "[--incremental] [--sync] [--lang zh|en] [--acknowledge-ethical-use]")
        print("       clawithme watch <username> [--interval 6h|12h|24h] "
              "[--include-migrated] [--webhook <url>] [--acknowledge-ethical-use]")
        print("       clawithme linkedin-login")
        print("       clawithme tui")
        print("       clawithme verify")
        print("       clawithme validate")
        sys.exit(1)

    command = sys.argv[1]

    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: clawithme search <username> [--report <path>] "
                  "[--format html|json|pdf|md] [--include-migrated] [--no-cache] "
                  "[--sync] [--lang zh|en] [--acknowledge-ethical-use]")
            sys.exit(1)
        username = sys.argv[2]
        report_path = None
        report_format = "html"
        report_lang = "zh"
        include_migrated = "--include-migrated" in sys.argv
        no_cache = "--no-cache" in sys.argv
        incremental = "--incremental" in sys.argv
        acknowledged = "--acknowledge-ethical-use" in sys.argv
        async_mode = "--sync" not in sys.argv
        if "--report" in sys.argv:
            idx = sys.argv.index("--report")
            if idx + 1 < len(sys.argv):
                report_path = sys.argv[idx + 1]
        if "--format" in sys.argv:
            idx = sys.argv.index("--format")
            if idx + 1 < len(sys.argv):
                report_format = sys.argv[idx + 1]
        if "--lang" in sys.argv:
            idx = sys.argv.index("--lang")
            if idx + 1 < len(sys.argv):
                report_lang = sys.argv[idx + 1]
        if report_lang not in ("zh", "en"):
            print(f"❌ Unknown lang: {report_lang!r}. Use 'zh' or 'en'.")
            sys.exit(1)
        if report_format not in ("html", "json", "pdf", "md"):
            print(f"❌ Unknown format: {report_format!r}. Use 'html', 'json', 'pdf', or 'md'.")
            sys.exit(1)
        search(username, report_path=report_path, report_format=report_format,
               include_migrated=include_migrated, acknowledged=acknowledged,
               no_cache=no_cache, incremental=incremental,
               async_mode=async_mode, lang=report_lang)

    elif command == "linkedin-login":
        """Interactive LinkedIn login — capture cookies via browser."""
        from clawithme.linkedin_auth import run_linkedin_login

        sys.exit(run_linkedin_login())

    elif command == "tui":
        """Launch the interactive Terminal UI."""
        from clawithme.tui.app import TUIApp

        TUIApp().run()

    elif command == "verify":
        # Delegate to verify_site.py
        import subprocess
        script = Path(__file__).resolve().parent.parent / "scripts" / "verify_site.py"
        args = [sys.executable, str(script), "--all"]
        if len(sys.argv) > 2:
            args = [sys.executable, str(script), sys.argv[2]]
        subprocess.run(args, check=False)  # verify script exits non-zero on failures

    elif command == "watch":
        """Periodic monitoring with change detection."""
        import asyncio as _asyncio
        from clawithme.watch import Watcher

        if len(sys.argv) < 3:
            print("Usage: clawithme watch <username> [--interval 6h|12h|24h] "
                  "[--include-migrated] [--webhook <url>] [--acknowledge-ethical-use]")
            sys.exit(1)

        username = sys.argv[2]
        if not acknowledged:
            acknowledged = "--acknowledge-ethical-use" in sys.argv
        if not acknowledged:
            print("🛡️  ETHICAL USE REQUIRED")
            print()
            print("   This tool queries public profiles and breach databases.")
            print("   Use only on accounts you own or have explicit authorization.")
            print()
            print("   Re-run with: clawithme watch <username> --acknowledge-ethical-use")
            return

        interval_hours = 24
        if "--interval" in sys.argv:
            idx = sys.argv.index("--interval")
            if idx + 1 < len(sys.argv):
                raw = sys.argv[idx + 1].rstrip("h")
                try:
                    interval_hours = int(raw)
                except ValueError:
                    print(f"❌ Invalid interval: {sys.argv[idx + 1]!r}. Use e.g. 6h, 12h, 24h")
                    sys.exit(1)

        include_migrated = "--include-migrated" in sys.argv

        webhook_url = None
        if "--webhook" in sys.argv:
            idx = sys.argv.index("--webhook")
            if idx + 1 < len(sys.argv):
                webhook_url = sys.argv[idx + 1]

        watcher = Watcher(
            username,
            interval_hours=interval_hours,
            include_migrated=include_migrated,
            webhook_url=webhook_url,
        )
        _asyncio.run(watcher.run())

    elif command == "validate":
        print("Validating site definitions against schema...")
        sites = load_all_sites(validate=True)
        print(f"  Loaded {len(sites)} sites with schema validation (warnings above)")

    else:
        print(f"Unknown command: {command}")
        print("Usage: clawithme search <username>")
        print("       clawithme watch <username> [--interval 6h|12h|24h]")
        print("       clawithme tui")
        print("       clawithme verify")
        print("       clawithme validate")
        sys.exit(1)


if __name__ == "__main__":
    main()
