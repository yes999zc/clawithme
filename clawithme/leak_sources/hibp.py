"""HIBPSource — HaveIBeenPwned breach database integration.

Uses HIBP API v3 for email breach lookups (requires API key + subscription).
Falls back gracefully if no API key configured.
"""

from __future__ import annotations

import asyncio

from clawithme.engine.http_client import HttpClient
from clawithme.leak_sources import BreachRecord, LeakSource
from clawithme.logging import get_logger

HIBP_API_BASE = "https://haveibeenpwned.com/api/v3"

logger = get_logger()


class HIBPSource(LeakSource):
    """HaveIBeenPwned breach database — requires API key for email search.

    API v3 docs: https://haveibeenpwned.com/API/v3
    Requires a verified API key ($3.50/month subscription).
    """

    def __init__(self, api_key: str = "", base_url: str | None = None):
        self._api_key = api_key
        self._base = base_url or HIBP_API_BASE
        self._http: HttpClient | None = None

    def _get_client(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(timeout_ms=10000)
        return self._http

    def _headers(self) -> dict[str, str]:
        return {
            "hibp-api-key": self._api_key,
            "User-Agent": "clawithme",
        }

    async def _async_get(self, path: str) -> tuple[int, str]:
        """Run HttpClient.get in a thread, return (status_code, body)."""
        client = self._get_client()
        url = f"{self._base}{path}"
        resp = await asyncio.to_thread(client.get, url, headers=self._headers())
        return resp.status_code, resp.text

    # ── Core search methods ────────────────────────────────

    async def search_by_email(self, email: str) -> list[BreachRecord]:
        """Query HIBP for breaches associated with an email address.

        Requires a verified API key. Returns empty list if no key or no breaches.
        """
        if not self._api_key:
            logger.debug("hibp_no_api_key", email=email)
            return []

        try:
            status, body = await self._async_get(
                f"/breachedaccount/{email}?truncateResponse=false"
            )
        except (OSError, ValueError, TimeoutError) as e:
            logger.warning("hibp_request_failed", email=email, error=str(e))
            return []

        if status == 404:
            # 404 = email not found in any breach (not an error)
            logger.debug("hibp_no_breaches", email=email)
            return []
        if status == 401:
            logger.warning("hibp_unauthorized", email=email)
            return []
        if status == 429:
            logger.warning("hibp_rate_limited", email=email)
            return []
        if status != 200:
            logger.warning("hibp_unexpected_status", status=status, email=email)
            return []

        try:
            import json
            breaches = json.loads(body)
        except json.JSONDecodeError as e:
            logger.warning("hibp_parse_error", email=email, error=str(e))
            return []

        records: list[BreachRecord] = []
        for b in breaches:
            records.append(BreachRecord(
                email=email,
                domain=b.get("Domain", ""),
                source=f"hibp:{b.get('Name', 'unknown')}",
                breach_date=b.get("BreachDate", ""),
            ))

        logger.info("hibp_search", email=email, records=len(records))
        return records

    async def search_by_username(self, username: str) -> list[BreachRecord]:
        """HIBP does not support username search — only email."""
        logger.debug("hibp_no_username_search", username=username)
        return []

    async def search_by_phone(self, phone: str) -> list[BreachRecord]:
        """HIBP does not support phone search."""
        logger.debug("hibp_no_phone_search", phone=phone)
        return []

    async def is_available(self) -> bool:
        """Check if HIBP API is reachable and key is valid."""
        if not self._api_key:
            return False
        try:
            status, _ = await self._async_get("/breachedaccount/test@example.com")
            return status in (200, 404)  # both mean API works
        except (OSError, ValueError, TimeoutError):
            return False

    async def rate_limit_remaining(self) -> int:
        """HIBP rate limit is per-API-key (typically 1 request per 1.5s)."""
        return -1  # HIBP doesn't expose rate limits in a queryable way

    async def close(self):
        """Release HTTP client reference."""
        self._http = None
