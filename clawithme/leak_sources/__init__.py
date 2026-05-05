"""LeakSource — abstract interface for breach/leak database queries.

Implements:
  1.4.1 BreachRecord Pydantic Model
  1.4.2 LeakSource abstract base class
  1.4.3 CavalierSource (Hudson Rock, free API)
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod

from pydantic import BaseModel, field_validator

from clawithme.engine.http_client import HttpClient, HttpResponse
from clawithme.logging import get_logger

logger = get_logger()


# ── 1.4.1 BreachRecord ──────────────────────────────────────────────

class BreachRecord(BaseModel):
    """A single breach/leak record.

    All fields Optional — different data sources return different fields.
    Uses Pydantic for auto-validation at construction time.
    password_sha256 only — never store plaintext passwords.
    """

    email: str | None = None
    username: str | None = None
    phone: str | None = None
    password_sha256: str | None = None
    domain: str | None = None
    source: str | None = None
    breach_date: str | None = None

    @field_validator("email")
    @classmethod
    def _validate_email(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v.strip()):
            raise ValueError(f"Invalid email format: {v!r}")
        return v.strip().lower()

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        digits = re.sub(r"\D", "", v)
        if len(digits) < 7 or len(digits) > 15:
            raise ValueError(f"Invalid phone number: {v!r}")
        return v

    @field_validator("password_sha256")
    @classmethod
    def _validate_sha256(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not re.match(r"^[a-f0-9]{64}$", v.lower()):
            raise ValueError(f"Invalid SHA-256 hash: {v!r}")
        return v.lower()

    def __str__(self) -> str:
        parts = []
        if self.email:
            parts.append(self.email)
        if self.username:
            parts.append(f"@{self.username}")
        if self.phone:
            parts.append(self.phone)
        if self.source:
            parts.append(f"[{self.source}]")
        return " ".join(parts) if parts else "<empty record>"


# ── 1.4.2 LeakSource ABC ────────────────────────────────────────────

class LeakSource(ABC):
    """Abstract base for breach database query sources."""

    @abstractmethod
    async def search_by_username(self, username: str) -> list[BreachRecord]:
        """Search for records associated with a username."""
        ...

    @abstractmethod
    async def search_by_email(self, email: str) -> list[BreachRecord]:
        """Search for records associated with an email."""
        ...

    @abstractmethod
    async def search_by_phone(self, phone: str) -> list[BreachRecord]:
        """Search for records associated with a phone number."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Health check — is this source reachable?"""
        ...

    @abstractmethod
    async def rate_limit_remaining(self) -> int:
        """Estimated remaining API calls before rate-limiting.
        Returns -1 if unknown.
        """
        ...


# ── 1.4.3 CavalierSource ────────────────────────────────────────────

CAVALIER_BASE = "https://cavalier.hudsonrock.com/api/json/v2"


class CavalierSource(LeakSource):
    """Hudson Rock Cavalier — free infostealer intelligence API.

    Endpoint: /osint-tools/search-by-username?username=xxx
    No API key required for basic search.
    """

    def __init__(self, base_url: str | None = None):
        self._base = base_url or CAVALIER_BASE
        self._http: HttpClient | None = None

    def _get_client(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(timeout_ms=15000)
        return self._http

    async def _async_get(self, url: str, params: dict | None = None) -> HttpResponse:
        """Run HttpClient.get in a thread to preserve async API."""
        client = self._get_client()
        full_url = url
        if params:
            query = "&".join(f"{k}={v}" for k, v in params.items())
            full_url = f"{url}?{query}"
        return await asyncio.to_thread(client.get, full_url)

    async def search_by_username(self, username: str) -> list[BreachRecord]:
        """Query Cavalier for infostealer records by username."""
        url = f"{self._base}/osint-tools/search-by-username"
        try:
            resp = await self._async_get(url, params={"username": username})
            if not resp.ok:
                logger.warning("cavalier_http_error", status=resp.status_code, username=username)
                return []

            import json
            data = json.loads(resp.text)

            records: list[BreachRecord] = []
            for stealer in data.get("stealers", []):
                records.append(BreachRecord(
                    username=username,
                    email=stealer.get("email"),
                    domain=stealer.get("domain"),
                    source=f"cavalier:{stealer.get('stealer_family', 'unknown')}",
                    breach_date=stealer.get("infection_date"),
                ))

            logger.info(
                "cavalier_search",
                username=username,
                records=len(records),
                corporate=data.get("total_corporate_services", 0),
                user=data.get("total_user_services", 0),
            )
            return records

        except (OSError, ValueError, TimeoutError) as e:
            logger.warning("cavalier_error", username=username, error=str(e))
            return []

    async def search_by_email(self, email: str) -> list[BreachRecord]:
        """Cavalier does not support direct email search."""
        logger.debug("cavalier_no_email_search", email=email)
        return []

    async def search_by_phone(self, phone: str) -> list[BreachRecord]:
        """Query Cavalier for infostealer records by phone number."""
        url = f"{self._base}/osint-tools/search-by-phone"
        try:
            resp = await self._async_get(url, params={"phone": phone})
            if not resp.ok:
                logger.warning("cavalier_phone_http_error", status=resp.status_code, phone=phone)
                return []

            import json
            data = json.loads(resp.text)

            records: list[BreachRecord] = []
            for stealer in data.get("stealers", []):
                records.append(BreachRecord(
                    phone=phone,
                    email=stealer.get("email"),
                    domain=stealer.get("domain"),
                    source=f"cavalier:{stealer.get('stealer_family', 'unknown')}",
                    breach_date=stealer.get("infection_date"),
                ))

            logger.info(
                "cavalier_phone_search",
                phone=phone,
                records=len(records),
            )
            return records

        except (OSError, ValueError, TimeoutError) as e:
            logger.warning("cavalier_phone_error", phone=phone, error=str(e))
            return []

    async def is_available(self) -> bool:
        """Check if Cavalier API is reachable."""
        try:
            resp = await self._async_get(
                f"{self._base}/osint-tools/search-by-username",
                params={"username": "test"},
            )
            return resp.status_code == 200
        except (OSError, ValueError, TimeoutError):
            return False

    async def rate_limit_remaining(self) -> int:
        """Cavalier does not expose rate limits in headers."""
        return -1

    async def close(self):
        """Release HTTP client reference."""
        self._http = None
