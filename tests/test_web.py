"""Tests for clawithme/web/app.py — FastAPI + SSE streaming."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from clawithme.web.app import _sse, app


class TestSSEHelper:
    def test_format(self):
        result = _sse("phase", '{"msg": "hello"}')
        assert result == 'event: phase\ndata: {"msg": "hello"}\n\n'

    def test_empty_data(self):
        result = _sse("done", "")
        assert result == "event: done\ndata: \n\n"


class TestIndexPage:
    @pytest.mark.anyio
    async def test_returns_html(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            resp = await client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "OSINT Identity Panorama" in resp.text
        assert "id=\"username\"" in resp.text


class TestSearchEndpoint:
    """SSE streaming endpoint tests."""

    @pytest.fixture
    def mock_pipeline(self):
        """Return a mock pipeline result with hits, profiles, and clusters."""
        result = MagicMock()
        result.hits = [
            {"site_id": "github", "site_name": "GitHub",
             "url": "https://github.com/testuser"},
        ]
        result.profiles = [
            {"site_id": "github", "display_name": "Test User",
             "location": "Shanghai", "bio": "Developer", "avatar_url": None,
             "follower_count": 42},
        ]

        # Create mock cluster
        from clawithme.crawler.base import Profile
        from clawithme.signals.correlation import Cluster

        p1 = Profile("github", "GitHub", "https://github.com/testuser", "testuser")
        p2 = Profile("zhihu", "知乎", "https://zhihu.com/testuser", "testuser")
        cluster = Cluster(profiles=[p1, p2], confidence=0.8,
                          signals=["username"], evidence={})
        result.clusters = [cluster]
        result.leak_records = []
        result.searxng_hits = 0
        return result

    @pytest.mark.anyio
    async def test_streams_hits_profiles_done(self, mock_pipeline):
        with (
            patch("clawithme.web.app.load_all_sites", return_value=[{"id": "github"}]),
            patch("clawithme.web.app.load_engines", return_value=[]),
            patch("clawithme.web.app.discover_extractors", return_value=[]),
            patch("clawithme.web.app.LLMVerifier") as mock_llm,
            patch("clawithme.web.app.AsyncPipeline") as MockPipeline,
        ):
            mock_llm.return_value.is_configured.return_value = False
            mock_instance = MockPipeline.return_value
            mock_instance.run = AsyncMock(return_value=mock_pipeline)

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/api/search/testuser?ethics=true")
                assert resp.status_code == 200

                events = _parse_sse(resp.text)

        assert any(e["event"] == "hit" for e in events)
        assert any(e["event"] == "profile" for e in events)
        assert any(e["event"] == "cluster" for e in events)

        done_events = [e for e in events if e["event"] == "done"]
        assert len(done_events) == 1
        done_data = _parse_json_safe(done_events[0]["data"])
        assert done_data["hits"] == 1
        assert done_data["profiles"] == 1

    @pytest.mark.anyio
    async def test_pipeline_error_graceful(self):
        with (
            patch("clawithme.web.app.load_all_sites", return_value=[{"id": "github"}]),
            patch("clawithme.web.app.load_engines", return_value=[]),
            patch("clawithme.web.app.discover_extractors", return_value=[]),
            patch("clawithme.web.app.LLMVerifier") as mock_llm,
            patch("clawithme.web.app.AsyncPipeline") as MockPipeline,
        ):
            mock_llm.return_value.is_configured.return_value = False
            mock_instance = MockPipeline.return_value
            mock_instance.run = AsyncMock(
                side_effect=OSError("Network unreachable"),
            )

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/api/search/testuser?ethics=true")
                assert resp.status_code == 200

                events = _parse_sse(resp.text)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "Pipeline failed: I/O error" in error_events[0]["data"]

    @pytest.mark.anyio
    async def test_generic_exception_caught(self):
        """Catch-all: unhandled exception types yield error event, not crash."""
        with (
            patch("clawithme.web.app.load_all_sites", return_value=[{"id": "github"}]),
            patch("clawithme.web.app.load_engines", return_value=[]),
            patch("clawithme.web.app.discover_extractors", return_value=[]),
            patch("clawithme.web.app.LLMVerifier") as mock_llm,
            patch("clawithme.web.app.AsyncPipeline") as MockPipeline,
        ):
            mock_llm.return_value.is_configured.return_value = False
            mock_instance = MockPipeline.return_value
            mock_instance.run = AsyncMock(side_effect=KeyError("missing_key"))

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/api/search/testuser?ethics=true")
                assert resp.status_code == 200

                events = _parse_sse(resp.text)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "KeyError" in error_events[0]["data"]

    @pytest.mark.anyio
    async def test_site_load_error_graceful(self):
        with patch(
            "clawithme.web.app.load_all_sites",
            side_effect=OSError("No such directory"),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/api/search/testuser?ethics=true")
                assert resp.status_code == 200

                events = _parse_sse(resp.text)

        error_events = [e for e in events if e["event"] == "error"]
        assert len(error_events) == 1
        assert "Failed to load site data" in error_events[0]["data"]

    @pytest.mark.anyio
    async def test_single_profile_cluster_omitted(self, mock_pipeline):
        """Single-profile clusters are NOT streamed (filtered in handler)."""
        # Remove p2 → cluster has only 1 profile → should be filtered
        mock_pipeline.clusters[0].profiles = mock_pipeline.clusters[0].profiles[:1]

        with (
            patch("clawithme.web.app.load_all_sites", return_value=[{"id": "github"}]),
            patch("clawithme.web.app.load_engines", return_value=[]),
            patch("clawithme.web.app.discover_extractors", return_value=[]),
            patch("clawithme.web.app.LLMVerifier") as mock_llm,
            patch("clawithme.web.app.AsyncPipeline") as MockPipeline,
        ):
            mock_llm.return_value.is_configured.return_value = False
            mock_instance = MockPipeline.return_value
            mock_instance.run = AsyncMock(return_value=mock_pipeline)

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test",
            ) as client:
                resp = await client.get("/api/search/testuser?ethics=true")
                assert resp.status_code == 200

                events = _parse_sse(resp.text)

        # Cluster filtered out because only 1 profile
        cluster_events = [e for e in events if e["event"] == "cluster"]
        assert len(cluster_events) == 0

        # Done event still shows clusters count
        done = [e for e in events if e["event"] == "done"]
        assert len(done) == 1


# ── Helpers ────────────────────────────────────────────────────

def _parse_sse(raw: str) -> list[dict]:
    """Parse raw SSE text into list of {event, data} dicts."""
    events = []
    current = {}
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current["event"] = line[7:]
        elif line.startswith("data: "):
            current["data"] = line[6:]
        elif line == "" and current:
            if "event" in current:
                events.append(current)
            current = {}
    if current and "event" in current:
        events.append(current)
    return events


def _parse_json_safe(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
