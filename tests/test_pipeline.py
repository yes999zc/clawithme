"""Tests for pipeline.py — async pipeline orchestrator."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from clawithme.cache import ResultCache
from clawithme.crawler.base import Profile
from clawithme.engine.engines import EngineResult
from clawithme.pipeline import AsyncPipeline, SearchResult

# ── Helpers ────────────────────────────────────────────────────

class FakeConfig:
    class apis:
        hibp_api_key = ""


def _make_site(site_id: str, probe_url: str = "https://{site}.com/{username}"):
    return {
        "id": site_id,
        "name": site_id.capitalize(),
        "urlMain": f"https://{site_id}.com",
        "domain": f"{site_id}.com",
        "check": {"probe_url": probe_url},
        "engine_ref": "base_http_status",
    }


def _hit_result(site_id, url="https://example.com/u"):
    return EngineResult(
        site_id=site_id, site_name=site_id.capitalize(),
        url_probed=url, status_code=200, exists=True,
        engine="status", classifier="status_code",
    )


def _miss_result(site_id, url="https://example.com/u"):
    return EngineResult(
        site_id=site_id, site_name=site_id.capitalize(),
        url_probed=url, status_code=404, exists=False,
        engine="status", classifier="status_code",
    )


# ── Tests ──────────────────────────────────────────────────────

class TestPipelineInit:
    def test_creates_search_result(self):
        _pipeline = AsyncPipeline([], {}, {}, FakeConfig())
        result = SearchResult()
        assert result.hits == []
        assert result.clusters == []


class TestProbeSites:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_probe(self):
        """Cache hit returns immediately without calling engine.probe."""
        sites = [_make_site("github")]
        engine = MagicMock()
        engines = {"base_http_status": engine}

        cache = MagicMock()
        cache.get.return_value = {
            "exists": True,
            "hit": {
                "site_id": "github", "site_name": "GitHub",
                "url": "https://github.com/alice", "status": 200,
                "site_def": sites[0],
            },
        }

        pipeline = AsyncPipeline(sites, engines, {}, FakeConfig(), cache=cache)
        hits = await pipeline._probe_sites("alice")

        assert len(hits) == 1
        assert hits[0]["site_id"] == "github"
        # Cache hit → engine.probe() was never called
        engine.probe.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_triggers_probe(self):
        """Cache miss fires engine.probe() and collects results."""
        sites = [_make_site("github")]
        engine = MagicMock()
        engine.probe.return_value = _hit_result("github")
        engines = {"base_http_status": engine}

        cache = MagicMock()
        cache.get.return_value = None  # cache miss

        pipeline = AsyncPipeline(sites, engines, {}, FakeConfig(), cache=cache)
        hits = await pipeline._probe_sites("alice")

        assert len(hits) == 1
        assert hits[0]["site_id"] == "github"
        assert cache.set.called

    @pytest.mark.asyncio
    async def test_probe_error_isolation(self):
        """One probe failure doesn't block other probes."""
        sites = [
            _make_site("github"),
            {"id": "broken", "name": "Broken", "urlMain": "https://broken.com",
             "domain": "broken.com", "check": {"probe_url": "https://broken.com/{username}"},
             "engine_ref": "base_http_message"},
        ]

        good_engine = MagicMock()
        good_engine.probe.return_value = _hit_result("github")
        bad_engine = MagicMock()
        bad_engine.probe.side_effect = OSError("Connection refused")

        engines = {
            "base_http_status": good_engine,
            "base_http_message": bad_engine,
        }

        pipeline = AsyncPipeline(sites, engines, {}, FakeConfig(), cache=None)
        hits = await pipeline._probe_sites("alice")

        # Broken site is skipped, github succeeds
        assert len(hits) == 1
        assert hits[0]["site_id"] == "github"

    @pytest.mark.asyncio
    async def test_no_cache_always_probes(self):
        """Without cache, all sites are probed every time."""
        sites = [_make_site("github")]
        engine = MagicMock()
        engine.probe.return_value = _hit_result("github")
        engines = {"base_http_status": engine}

        pipeline = AsyncPipeline(sites, engines, {}, FakeConfig(), cache=None)
        hits = await pipeline._probe_sites("alice")

        assert len(hits) == 1
        engine.probe.assert_called_once()

    @pytest.mark.asyncio
    async def test_nonexistent_user_no_hit(self):
        """Probe returning exists=False does NOT generate a hit."""
        sites = [_make_site("github")]
        engine = MagicMock()
        engine.probe.return_value = _miss_result("github")
        engines = {"base_http_status": engine}

        pipeline = AsyncPipeline(sites, engines, {}, FakeConfig(), cache=None)
        hits = await pipeline._probe_sites("nobody")

        assert len(hits) == 0


class TestExtractProfiles:
    @pytest.mark.asyncio
    async def test_extracts_from_hits(self):
        """Hits with matching extractors get profiles extracted."""
        hits = [{"site_id": "github", "site_def": {}, "url": "https://github.com/alice"}]

        profile = Profile(
            site_id="github", site_name="GitHub",
            url="https://github.com/alice", username="alice",
            display_name="Alice", bio="Dev", location="SF",
        )
        extractor = MagicMock()
        extractor.extract.return_value = profile
        extractors = {"github": MagicMock(return_value=extractor)}

        pipeline = AsyncPipeline([], {}, extractors, FakeConfig())
        profiles, p_objs = await pipeline._extract_profiles("alice", hits)

        assert len(profiles) == 1
        assert profiles[0]["display_name"] == "Alice"
        assert len(p_objs) == 1

    @pytest.mark.asyncio
    async def test_empty_profile_not_counted(self):
        """Empty profiles are returned as objects but not in profiles list."""
        hits = [{"site_id": "github", "site_def": {}, "url": "https://github.com/alice"}]

        empty_p = Profile(
            site_id="github", site_name="GitHub",
            url="https://github.com/alice", username="alice",
        )  # .empty == True
        extractor = MagicMock()
        extractor.extract.return_value = empty_p
        extractors = {"github": MagicMock(return_value=extractor)}

        pipeline = AsyncPipeline([], {}, extractors, FakeConfig())
        profiles, p_objs = await pipeline._extract_profiles("alice", hits)

        assert len(profiles) == 0
        assert len(p_objs) == 1  # still tracked for correlation

    @pytest.mark.asyncio
    async def test_extract_error_isolation(self):
        """One extractor failure doesn't block others."""
        hits = [
            {"site_id": "github", "site_def": {}, "url": "https://github.com/alice"},
            {"site_id": "broken", "site_def": {}, "url": "https://broken.com/alice"},
        ]

        good_profile = Profile(
            site_id="github", site_name="GitHub",
            url="https://github.com/alice", username="alice",
            display_name="Alice",
        )
        good_extractor = MagicMock()
        good_extractor.extract.return_value = good_profile
        bad_extractor = MagicMock()
        bad_extractor.extract.side_effect = OSError("Timeout")

        extractors = {
            "github": MagicMock(return_value=good_extractor),
            "broken": MagicMock(return_value=bad_extractor),
        }

        pipeline = AsyncPipeline([], {}, extractors, FakeConfig())
        profiles, p_objs = await pipeline._extract_profiles("alice", hits)

        assert len(profiles) == 1
        assert profiles[0]["site_id"] == "github"
        assert len(p_objs) == 1


class TestSyncFallback:
    """Verify sync mode still works (import-level test, no async)."""

    def test_sync_search_function_exists(self):
        from clawithme.cli import _search_sync
        assert callable(_search_sync)
