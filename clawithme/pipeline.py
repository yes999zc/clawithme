"""Phase 7 — Async pipeline orchestrator.

Replaces the serial search() god function with a staged async pipeline.
Each stage gates on the previous. Concurrency controlled by semaphores.

Pipeline: Cache → Probe (10× async) → SearXNG → Extract (5× async)
  → Leak DB → Correlation → SearchResult
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from clawithme.cache import ResultCache
from clawithme.crawler.base import Profile
from clawithme.engine.loader import get_engine_for_site
from clawithme.leak_sources import CavalierSource
from clawithme.leak_sources.hibp import HIBPSource
from clawithme.leak_sources.manager import query_breaches
from clawithme.logging import get_logger
from clawithme.signals.correlation import Cluster, CorrelationEngine

if TYPE_CHECKING:
    from clawithme.signals.llm_verifier import LLMVerifier

logger = get_logger()

# ── Probe semaphores ──────────────────────────────────────────
# These are module-level so ALL concurrent searches share limits.
_PROBE_SEM = asyncio.Semaphore(10)
_EXTRACT_SEM = asyncio.Semaphore(5)


@dataclass
class SearchResult:
    """Complete result of an async search pipeline run."""

    hits: list[dict] = field(default_factory=list)
    searxng_hits: int = 0
    profiles: list[dict] = field(default_factory=list)
    profile_objects: list[Profile] = field(default_factory=list)
    leak_records: list = field(default_factory=list)
    clusters: list[Cluster] = field(default_factory=list)


class AsyncPipeline:
    """Orchestrate username search across sites + leak DB asynchronously.

    Usage::

        pipeline = AsyncPipeline(sites, engines, extractors, config, cache=cache)
        result = await pipeline.run("alice")
        print(f"{len(result.hits)} hits, {len(result.clusters)} clusters")
    """

    def __init__(
        self,
        sites: list[dict],
        engines: dict,
        extractors: dict,
        config,
        cache: ResultCache | None = None,
        llm_verifier: "LLMVerifier | None" = None,
    ) -> None:
        self._sites = sites
        self._engines = engines
        self._extractors = extractors
        self._config = config
        self._cache = cache
        self._llm = llm_verifier

    # ── Public API ────────────────────────────────────────────

    async def run(self, username: str) -> SearchResult:
        """Execute full search pipeline and return aggregated result."""
        # Phase 1: Probe sites (async, cache-aware)
        hits = await self._probe_sites(username)

        # Phase 1.5: SearXNG fallback
        searxng_hits = await self._searxng_fallback(username, hits)

        # Phase 2: Extract profiles (async)
        profiles, profile_objects = await self._extract_profiles(username, hits)

        # Phase 3: Leak database
        leak_records = await self._query_leaks(username)

        # Phase 4: Correlation
        all_objects = list(profile_objects)
        for r in leak_records:
            all_objects.append(Profile(
                site_id=f"leak:{r.source or 'unknown'}",
                site_name=r.source or "Leak DB",
                url="",
                username=r.username or username,
                email=r.email,
                phone=r.phone,
            ))
        engine = CorrelationEngine(llm_verifier=self._llm)
        clusters = engine.correlate(all_objects)

        return SearchResult(
            hits=hits,
            searxng_hits=searxng_hits,
            profiles=profiles,
            profile_objects=profile_objects,
            leak_records=leak_records,
            clusters=clusters,
        )

    # ── Phase 1: Async Site Probing ───────────────────────────

    async def _probe_sites(self, username: str) -> list[dict]:
        """Probe all sites in parallel, bounded by _PROBE_SEM.

        Cache hits skip the probe entirely (sync check before gather).
        Cache misses fire async probes under semaphore control.
        Probe failures are isolated — one bad site doesn't kill others.
        """
        hits: list[dict] = []
        tasks: list[asyncio.Task] = []
        site_map: dict[int, dict] = {}  # task_index → site

        for site in self._sites:
            site_id = site["id"]
            cache_key = f"probe:{username}:{site_id}"

            # Cache hit — fast path, no async overhead
            if self._cache is not None:
                cached = self._cache.get(cache_key)
                if cached is not None:
                    if cached.get("exists"):
                        hits.append(cached["hit"])
                        logger.info("hit_cache", site=cached["hit"]["site_name"])
                    continue  # skip probe

            # Cache miss — schedule async probe
            idx = len(tasks)
            site_map[idx] = site
            tasks.append(asyncio.create_task(
                self._probe_one(site, username, cache_key)
            ))

        if not tasks:
            return hits

        # Fire all probes, wait for completion
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                site_id = site_map[i].get("id", "?")
                logger.warning(
                    "probe_error", site_id=site_id, error=str(result)
                )
                continue
            if result is not None:
                hits.append(result)

        return hits

    async def _probe_one(
        self, site: dict, username: str, cache_key: str | None = None
    ) -> dict | None:
        """Probe a single site under semaphore control.

        Returns the hit dict if the user exists, None otherwise.
        Writes to cache on both hit and miss (if cache is configured).
        """
        site_id = site["id"]

        async with _PROBE_SEM:
            engine = get_engine_for_site(site, self._engines)
            if engine is None:
                logger.warning("engine_missing", site_id=site_id)
                return None

            try:
                # engine.probe() is sync (Scrapling) — run in thread pool
                result = await asyncio.to_thread(
                    engine.probe, site, username
                )
            except ValueError as e:
                logger.warning(
                    "probe_template_error", site_id=site_id, error=str(e)
                )
                return None
            except (OSError, TimeoutError) as e:
                logger.warning(
                    "probe_network_error", site_id=site_id, error=str(e)
                )
                return None

        if result.exists:
            hit = {
                "site_id": result.site_id,
                "site_name": result.site_name,
                "url": result.url_probed,
                "status": result.status_code,
                "site_def": site,
            }
            if self._cache is not None and cache_key is not None:
                self._cache.set(cache_key, {"exists": True, "hit": hit})
            logger.info("hit", site=result.site_name, status=result.status_code)
            return hit

        # Don't cache probe failures (errors) — a transient network issue
        # should not block re-probing for 24 hours.
        if result.error:
            logger.debug("probe_error_not_cached", site=result.site_name, error=result.error)
            return None

        # Legitimate negative (user genuinely doesn't exist on this site).
        # Use shorter TTL (1h) for negatives — positive hits are stable, but a
        # negative could be caused by site changes, anti-bot blocks (403), or
        # rate limits (429) that the classifier can't distinguish from true 404s.
        if self._cache is not None and cache_key is not None:
            self._cache.set(cache_key, {"exists": False}, ttl_seconds=3600)
        return None

    # ── Phase 1.5: SearXNG Fallback ────────────────────────────

    async def _searxng_fallback(
        self, username: str, engine_hits: list[dict]
    ) -> int:
        """Query local SearXNG for un-hit sites. Returns count of new hits."""
        hit_ids = {h["site_id"] for h in engine_hits}
        searxng_base = "http://localhost:8888/search"
        total = 0

        for site in self._sites[:50]:  # cap: first 50 un-hit sites
            sid = site["id"]
            if sid in hit_ids:
                continue
            domain = site.get("domain") or site.get("urlMain", "")
            if not domain:
                continue
            if "://" in domain:
                domain = domain.split("://")[-1].split("/")[0]

            query = f'site:{domain} "{username}"'
            url = f"{searxng_base}?q={urllib.parse.quote(query)}&format=json"

            try:
                loop = asyncio.get_running_loop()
                data = await loop.run_in_executor(
                    None,
                    lambda u=url: json.loads(urllib.request.urlopen(u, timeout=5).read()),
                )
                results = data.get("results", [])
                if results:
                    engine_hits.append({
                        "site_id": sid,
                        "site_name": site.get("name", sid),
                        "url": results[0].get("url", ""),
                        "status": 0,
                        "site_def": site,
                    })
                    total += 1
            except (OSError, ValueError, TimeoutError, json.JSONDecodeError):
                continue

        return total

    # ── Phase 2: Async Profile Extraction ─────────────────────

    async def _extract_profiles(
        self, username: str, hits: list[dict]
    ) -> tuple[list[dict], list[Profile]]:
        """Extract profiles from hits in parallel, bounded by _EXTRACT_SEM."""
        profiles: list[dict] = []
        profile_objects: list[Profile] = []

        tasks: list[asyncio.Task] = []
        for hit in hits:
            site_id = hit["site_id"]
            extractor_cls = self._extractors.get(site_id)
            if extractor_cls is None:
                continue
            tasks.append(asyncio.create_task(
                self._extract_one(extractor_cls, hit, username)
            ))

        if not tasks:
            return profiles, profile_objects

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning("extract_error", error=str(result))
                continue
            if result is None:
                continue
            profile_dict, profile_obj = result
            profile_objects.append(profile_obj)
            if not profile_obj.empty:
                profiles.append(profile_dict)

        return profiles, profile_objects

    async def _extract_one(
        self, extractor_cls, hit: dict, username: str
    ) -> tuple[dict, Profile] | None:
        """Extract a single profile under semaphore control."""
        site_id = hit["site_id"]

        async with _EXTRACT_SEM:
            try:
                extractor = extractor_cls()
                # extract() is sync — run in thread pool
                profile = await asyncio.to_thread(
                    extractor.extract, hit["site_def"], username
                )
            except (OSError, ValueError, TimeoutError) as e:
                logger.warning(
                    "extract_failed", site=site_id, error=str(e)
                )
                return None

        profile_dict = {
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
            "empty": profile.empty,
        }

        if not profile.empty:
            logger.debug(
                "profile_extracted", site=site_id,
                display_name=profile.display_name,
            )

        return profile_dict, profile

    # ── Phase 3: Leak Database ────────────────────────────────

    async def _query_leaks(self, username: str) -> list:
        """Query Cavalier + HIBP (if configured) for breach records."""
        sources: list = [CavalierSource()]
        if self._config.apis.hibp_api_key:
            sources.append(HIBPSource(api_key=self._config.apis.hibp_api_key))

        try:
            records = await query_breaches(sources, username=username)
            # Follow-up: query by leaked email
            emails_found = [r.email for r in records if r.email]
            if emails_found:
                email_records = await query_breaches(
                    sources, email=emails_found[0]
                )
                records.extend(email_records)
            # Follow-up: query by leaked phone
            phones_found = [r.phone for r in records if r.phone]
            if phones_found:
                phone_records = await query_breaches(
                    sources, phone=phones_found[0]
                )
                records.extend(phone_records)
        except (OSError, ValueError, TimeoutError, RuntimeError) as e:
            logger.warning("leak_query_failed", error=str(e))
            records = []
        finally:
            for src in sources:
                with contextlib.suppress(Exception):
                    await src.close()

        return records
