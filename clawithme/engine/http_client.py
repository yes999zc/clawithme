"""Unified HTTP client backed by Scrapling Fetcher.

Replaces maigret's native requests/httpx with anti-bot fingerprinting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from scrapling import Fetcher

from clawithme.logging import get_logger

logger = get_logger()


@dataclass
class HttpResponse:
    """Unified response object — abstracts away Scrapling specifics."""

    status_code: int
    url: str
    text: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 400

    @property
    def is_redirect(self) -> bool:
        return 300 <= self.status_code < 400

    @property
    def is_not_found(self) -> bool:
        return self.status_code == 404


class HttpClient:
    """HTTP client with Scrapling anti-bot fingerprinting."""

    def __init__(
        self,
        proxy: str | None = None,
        timeout_ms: int = 5000,
        trace_id: str | None = None,
    ):
        self._log = get_logger(trace_id=trace_id) if trace_id else logger
        # Scrapling Fetcher auto-handles TLS fingerprints
        fetcher_kwargs: dict[str, Any] = {}
        if proxy:
            fetcher_kwargs["proxy"] = proxy
        self._fetcher = Fetcher(**fetcher_kwargs)
        self._timeout_ms = timeout_ms

    @property
    def static(self) -> Fetcher:
        """Underlying Scrapling Fetcher instance (for raw Response access)."""
        return self._fetcher

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        """HTTP GET with anti-bot fingerprinting."""
        self._log.debug("http.get", url=url)
        timeout = max(1, self._timeout_ms // 1000)
        kwargs: dict[str, Any] = {"timeout": timeout}
        if headers:
            kwargs["headers"] = headers
        page = self._fetcher.get(url, **kwargs)
        return self._to_response(page)

    def head(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        """HTTP HEAD — uses GET as fallback (Scrapling has no native HEAD).

        For our use case (presence detection), GET with lightweight response
        handling is functionally equivalent to HEAD.
        """
        self._log.debug("http.head", url=url)
        timeout = max(1, self._timeout_ms // 1000)
        kwargs: dict[str, Any] = {"timeout": timeout}
        if headers:
            kwargs["headers"] = headers
        # Scrapling Fetcher doesn't have a head() method; use GET with stream-ish
        # For our use case, HEAD ≈ lightweight GET (we only care about status)
        page = self._fetcher.get(url, **kwargs)
        return self._to_response(page)

    def post(
        self, url: str, data: dict | None = None, headers: dict[str, str] | None = None
    ) -> HttpResponse:
        """HTTP POST."""
        self._log.debug("http.post", url=url)
        timeout = max(1, self._timeout_ms // 1000)
        kwargs: dict[str, Any] = {"timeout": timeout}
        if headers:
            kwargs["headers"] = headers
        if data:
            kwargs["data"] = data
        page = self._fetcher.post(url, **kwargs)
        return self._to_response(page)

    @staticmethod
    def _to_response(page) -> HttpResponse:
        """Convert Scrapling page to unified HttpResponse.

        Scrapling's Fetcher.text is a lazy TextHandler — str() on it may
        return empty string while body has the actual content. Fallback
        to decoding body with detected encoding.
        """
        body = page.body if page.body else b""
        text = str(page.text) if page.text else ""
        if not text and body:
            encoding = page.encoding if hasattr(page, "encoding") and page.encoding else "utf-8"
            try:
                text = body.decode(encoding, errors="replace")
            except (LookupError, UnicodeDecodeError):
                text = body.decode("utf-8", errors="replace")
        return HttpResponse(
            status_code=page.status,
            url=str(page.url),
            text=text,
            headers=dict(page.headers) if page.headers else {},
            body=body,
        )

    def close(self) -> None:
        """Release underlying resources (no-op — Scrapling Fetcher is ephemeral)."""
        pass
