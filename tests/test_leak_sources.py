"""Tests for Phase 3 leak sources — BreachRecord, Cavalier, HIBP, manager."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest

from clawithme.engine.http_client import HttpResponse
from clawithme.leak_sources import BreachRecord, CavalierSource
from clawithme.leak_sources.hibp import HIBPSource
from clawithme.leak_sources.manager import query_breaches

# ── BreachRecord validation ──────────────────────────────────────

class TestBreachRecord:
    def test_minimal_record(self):
        r = BreachRecord()
        assert r.email is None
        assert r.username is None
        assert r.phone is None

    def test_valid_email(self):
        r = BreachRecord(email="alice@gmail.com")
        assert r.email == "alice@gmail.com"

    def test_email_normalized_to_lowercase(self):
        r = BreachRecord(email="Alice@Gmail.COM")
        assert r.email == "alice@gmail.com"

    def test_invalid_email_raises(self):
        with pytest.raises(ValueError, match="Invalid email"):
            BreachRecord(email="not-an-email")

    def test_valid_phone(self):
        r = BreachRecord(phone="+86 13800001234")
        assert r.phone == "+86 13800001234"

    def test_phone_too_short_raises(self):
        with pytest.raises(ValueError, match="Invalid phone"):
            BreachRecord(phone="12345")

    def test_phone_too_long_raises(self):
        with pytest.raises(ValueError, match="Invalid phone"):
            BreachRecord(phone="1" * 16)

    def test_valid_sha256(self):
        h = "a" * 64
        r = BreachRecord(password_sha256=h)
        assert r.password_sha256 == h

    def test_sha256_normalized_to_lower(self):
        r = BreachRecord(password_sha256="A" * 64)
        assert r.password_sha256 == "a" * 64

    def test_invalid_sha256_raises(self):
        with pytest.raises(ValueError, match="Invalid SHA-256"):
            BreachRecord(password_sha256="not-hex")

        with pytest.raises(ValueError, match="Invalid SHA-256"):
            BreachRecord(password_sha256="a" * 63)  # 63 ≠ 64

    def test_str_representation(self):
        r = BreachRecord(email="a@b.com", username="test", source="cavalier")
        s = str(r)
        assert "a@b.com" in s
        assert "@test" in s
        assert "[cavalier]" in s

    def test_str_empty_record(self):
        assert str(BreachRecord()) == "<empty record>"

    def test_domain_field(self):
        r = BreachRecord(domain="github.com")
        assert r.domain == "github.com"


# ── CavalierSource ───────────────────────────────────────────────

CAVALIER_USERNAME_RESPONSE = {
    "stealers": [
        {
            "email": "alice@gmail.com",
            "domain": "github.com",
            "stealer_family": "RedLine",
            "infection_date": "2024-03-15",
        },
        {
            "email": "alice@outlook.com",
            "domain": "twitter.com",
            "stealer_family": "Vidar",
            "infection_date": "2024-06-01",
        },
    ],
    "total_corporate_services": 2,
    "total_user_services": 5,
}

CAVALIER_PHONE_RESPONSE = {
    "stealers": [
        {
            "email": "bob@gmail.com",
            "domain": "dropbox.com",
            "stealer_family": "RedLine",
            "infection_date": "2024-01-10",
        },
    ],
}


def _make_http_response(status: int, body: str | dict, url: str = "") -> HttpResponse:
    """Helper: build an HttpResponse from status + body."""
    text = json.dumps(body) if isinstance(body, dict) else body
    return HttpResponse(status_code=status, url=url or "http://test", text=text)


@pytest.mark.asyncio
class TestCavalierSource:
    async def test_search_by_username_returns_records(self):
        source = CavalierSource()
        mock_resp = _make_http_response(200, CAVALIER_USERNAME_RESPONSE)

        with patch.object(source, "_async_get", AsyncMock(return_value=mock_resp)):
            records = await source.search_by_username("alice")

        assert len(records) == 2
        assert records[0].email == "alice@gmail.com"
        assert records[0].domain == "github.com"
        assert records[0].source == "cavalier:RedLine"
        assert records[0].breach_date == "2024-03-15"

    async def test_search_by_username_empty(self):
        source = CavalierSource()
        mock_resp = _make_http_response(200, {"stealers": []})

        with patch.object(source, "_async_get", AsyncMock(return_value=mock_resp)):
            records = await source.search_by_username("nobody")

        assert records == []

    async def test_search_by_username_http_error(self):
        source = CavalierSource()
        mock_resp = _make_http_response(500, "Internal Server Error")

        with patch.object(source, "_async_get", AsyncMock(return_value=mock_resp)):
            records = await source.search_by_username("alice")

        assert records == []

    async def test_search_by_phone_returns_records(self):
        source = CavalierSource()
        mock_resp = _make_http_response(200, CAVALIER_PHONE_RESPONSE)

        with patch.object(source, "_async_get", AsyncMock(return_value=mock_resp)):
            records = await source.search_by_phone("13800001234")

        assert len(records) == 1
        assert records[0].email == "bob@gmail.com"
        assert records[0].phone == "13800001234"

    async def test_search_by_phone_http_error(self):
        source = CavalierSource()
        mock_resp = _make_http_response(500, "error")

        with patch.object(source, "_async_get", AsyncMock(return_value=mock_resp)):
            records = await source.search_by_phone("13800001234")

        assert records == []

    async def test_search_by_email_returns_empty(self):
        """Cavalier does not support email search."""
        source = CavalierSource()
        records = await source.search_by_email("alice@gmail.com")
        assert records == []

    async def test_is_available(self):
        source = CavalierSource()
        mock_resp = _make_http_response(200, {})

        with patch.object(source, "_async_get", AsyncMock(return_value=mock_resp)):
            assert await source.is_available() is True

    async def test_is_not_available_on_error(self):
        source = CavalierSource()

        with patch.object(source, "_async_get", AsyncMock(side_effect=OSError("down"))):
            assert await source.is_available() is False

    async def test_rate_limit_unknown(self):
        source = CavalierSource()
        assert await source.rate_limit_remaining() == -1


# ── HIBPSource ───────────────────────────────────────────────────

HIBP_BREACHES_RESPONSE = [
    {"Name": "Adobe", "Domain": "adobe.com", "BreachDate": "2013-10-04"},
    {"Name": "LinkedIn", "Domain": "linkedin.com", "BreachDate": "2012-05-05"},
]


@pytest.mark.asyncio
class TestHIBPSource:
    async def test_search_by_email_no_api_key(self):
        source = HIBPSource(api_key="")
        records = await source.search_by_email("test@example.com")
        assert records == []

    async def test_search_by_email_returns_records(self):
        source = HIBPSource(api_key="test-key")
        body = json.dumps(HIBP_BREACHES_RESPONSE)

        with patch.object(source, "_async_get", AsyncMock(return_value=(200, body))):
            records = await source.search_by_email("alice@adobe.com")

        assert len(records) == 2
        assert records[0].email == "alice@adobe.com"
        assert records[0].domain == "adobe.com"
        assert records[0].source == "hibp:Adobe"

    async def test_search_by_email_404_no_breaches(self):
        source = HIBPSource(api_key="test-key")

        with patch.object(source, "_async_get", AsyncMock(return_value=(404, ""))):
            records = await source.search_by_email("clean@example.com")

        assert records == []

    async def test_search_by_email_401_unauthorized(self):
        source = HIBPSource(api_key="bad-key")

        with patch.object(source, "_async_get", AsyncMock(return_value=(401, ""))):
            records = await source.search_by_email("test@example.com")

        assert records == []

    async def test_search_by_email_429_rate_limited(self):
        source = HIBPSource(api_key="test-key")

        with patch.object(source, "_async_get", AsyncMock(return_value=(429, ""))):
            records = await source.search_by_email("test@example.com")

        assert records == []

    async def test_search_by_email_500_error(self):
        source = HIBPSource(api_key="test-key")

        with patch.object(source, "_async_get", AsyncMock(return_value=(500, "error"))):
            records = await source.search_by_email("test@example.com")

        assert records == []

    async def test_search_by_email_parse_error(self):
        source = HIBPSource(api_key="test-key")

        with patch.object(source, "_async_get", AsyncMock(return_value=(200, "not json"))):
            records = await source.search_by_email("test@example.com")

        assert records == []

    async def test_search_by_username_unsupported(self):
        source = HIBPSource(api_key="test-key")
        records = await source.search_by_username("testuser")
        assert records == []

    async def test_search_by_phone_unsupported(self):
        source = HIBPSource(api_key="test-key")
        records = await source.search_by_phone("13800001234")
        assert records == []

    async def test_is_available_no_key(self):
        source = HIBPSource(api_key="")
        assert await source.is_available() is False

    async def test_is_available_with_key(self):
        source = HIBPSource(api_key="test-key")

        with patch.object(source, "_async_get", AsyncMock(return_value=(404, ""))):
            # 404 means API is reachable, just no breaches for test@example.com
            assert await source.is_available() is True

    async def test_is_available_network_error(self):
        source = HIBPSource(api_key="test-key")

        with patch.object(source, "_async_get", AsyncMock(side_effect=OSError("down"))):
            assert await source.is_available() is False


# ── Manager (parallel query + dedup) ────────────────────────────

class FakeSource:
    """Minimal LeakSource for testing manager orchestration."""

    def __init__(self, name: str, records: list[BreachRecord], delay: float = 0):
        self.name = name
        self._records = records
        self._delay = delay

    async def search_by_username(self, username: str) -> list[BreachRecord]:
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._records

    async def search_by_email(self, email: str) -> list[BreachRecord]:
        return []

    async def search_by_phone(self, phone: str) -> list[BreachRecord]:
        return []

    async def is_available(self) -> bool:
        return True

    async def rate_limit_remaining(self) -> int:
        return -1


@pytest.mark.asyncio
class TestManager:
    async def test_parallel_query_merges_results(self):
        s1 = FakeSource("A", [
            BreachRecord(email="a@b.com", source="A"),
        ])
        s2 = FakeSource("B", [
            BreachRecord(email="c@d.com", source="B"),
            BreachRecord(email="e@f.com", source="B"),
        ])
        records = await query_breaches([s1, s2], username="test")
        assert len(records) == 3

    async def test_deduplicate_by_email_source(self):
        s1 = FakeSource("A", [
            BreachRecord(email="dup@b.com", source="A"),
        ])
        s2 = FakeSource("B", [
            BreachRecord(email="dup@b.com", source="A"),  # same key
            BreachRecord(email="unique@b.com", source="B"),
        ])
        records = await query_breaches([s1, s2], username="test")
        assert len(records) == 2  # dup@b.com:A deduplicated

    async def test_empty_sources(self):
        records = await query_breaches([], username="test")
        assert records == []

    async def test_source_failure_does_not_block_others(self):
        class FailingSource:
            async def search_by_username(self, username):
                raise OSError("boom")
            async def search_by_email(self, email):
                return []
            async def search_by_phone(self, phone):
                return []
            async def is_available(self):
                return True
            async def rate_limit_remaining(self):
                return -1

        good = FakeSource("Good", [BreachRecord(email="ok@b.com", source="Good")])
        bad = FailingSource()
        records = await query_breaches([good, bad], username="test")
        assert len(records) == 1
        assert records[0].email == "ok@b.com"

    async def test_source_timeout_does_not_block_others(self):
        slow = FakeSource("Slow", [BreachRecord(email="late@b.com")], delay=999)
        fast = FakeSource("Fast", [BreachRecord(email="fast@b.com", source="Fast")])
        records = await query_breaches([slow, fast], username="test", timeout=0.05)
        assert len(records) == 1
        assert records[0].email == "fast@b.com"

    async def test_email_query_routes_correctly(self):
        s = FakeSource("Test", [])
        # query_breaches with email= should call search_by_email, not search_by_username
        records = await query_breaches([s], email="test@example.com")
        assert records == []

    async def test_phone_query_routes_correctly(self):
        s = FakeSource("Test", [])
        records = await query_breaches([s], phone="13800001234")
        assert records == []
