"""Crawler HTTP client — delegates static fetching to engine's HttpClient.

Includes rate limiting, exponential backoff, and User-Agent rotation.
"""

from __future__ import annotations

import secrets
import time
from urllib.parse import urlparse

from scrapling.engines.toolbelt.custom import Response

from clawithme.engine.http_client import HttpClient
from clawithme.logging import get_logger

logger = get_logger()

# Lazy import — Playwright is heavy
_DYNAMIC_AVAILABLE: bool | None = None

# Remove navigator.webdriver flag (standard headless detection vector)
def _stealth_page_setup(page):
    """Inject anti-detection scripts into Playwright page before navigation."""
    page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    """)


def _make_page_setup(cookies: list[dict] | None = None):
    """Return a page_setup callback that injects cookies before navigation."""

    def setup(page):
        _stealth_page_setup(page)
        if cookies:
            try:
                page.context.add_cookies(cookies)
            except Exception:
                # Some cookies may fail (wrong domain); non-fatal
                pass

    return setup

# Common User-Agent strings for rotation
_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.2 Safari/605.1.15",
]


def _check_dynamic() -> bool:
    global _DYNAMIC_AVAILABLE
    if _DYNAMIC_AVAILABLE is None:
        try:
            from scrapling import DynamicFetcher  # noqa: F401
            _DYNAMIC_AVAILABLE = True
        except ImportError:
            logger.warning("dynamic_fetcher_unavailable")
            _DYNAMIC_AVAILABLE = False
    return _DYNAMIC_AVAILABLE


def random_user_agent() -> str:
    """Return a random User-Agent string from the rotation pool."""
    return secrets.choice(_USER_AGENTS)


_RETRYABLE_STATUSES = frozenset({429, 503})


def _parse_retry_after(response) -> float | None:
    """Parse Retry-After header (seconds or HTTP-date) → seconds or None."""
    value = response.headers.get("Retry-After", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        # HTTP-date format — approximate
        return None


# Module-level — shared across all CrawlerClient instances
_last_request_at: float = 0.0


class CrawlerClient:
    """HTTP client for profile extraction with rate limiting and UA rotation.

    Delegates static fetching to engine's HttpClient.
    Adds DynamicFetcher for JS-rendered pages (lazy init).

    Rate limiting is global — all CrawlerClient instances share
    a single inter-request delay timer to prevent burst patterns.
    """

    def __init__(
        self,
        timeout_ms: int = 30000,
        min_delay_ms: int = 200,
        max_retries: int = 2,
        backoff_base_ms: int = 1000,
        proxy: str | None = None,
    ):
        self._timeout_ms = timeout_ms
        self._min_delay_ms = min_delay_ms
        self._max_retries = max_retries
        self._backoff_base_ms = backoff_base_ms
        self._proxy = proxy
        self._http: HttpClient | None = None
        self._dynamic = None  # DynamicFetcher, lazy

    # ── Rate limiting ────────────────────────────────────────

    def _wait_if_needed(self):
        """Enforce minimum delay between requests (global, across instances)."""
        global _last_request_at
        elapsed = (time.monotonic() - _last_request_at) * 1000
        if elapsed < self._min_delay_ms:
            time.sleep((self._min_delay_ms - elapsed) / 1000)
        _last_request_at = time.monotonic()

    # ── HttpClient access ────────────────────────────────────

    @property
    def http(self) -> HttpClient:
        if self._http is None:
            self._http = HttpClient(timeout_ms=self._timeout_ms, proxy=self._proxy)
        return self._http

    @property
    def dynamic(self):
        if not _check_dynamic():
            return None
        if self._dynamic is None:
            from scrapling import DynamicFetcher
            self._dynamic = DynamicFetcher
        return self._dynamic

    # ── Robots.txt compliance (optional, opt-in per extractor) ─

    _robots_cache: dict[str, set[str]] = {}  # domain → disallowed path prefixes (shared class-level)

    def _parse_robots(self, text: str) -> set[str]:
        """Extract Disallow rules from User-agent: * section."""
        disallowed: set[str] = set()
        in_wildcard = False
        for line in text.splitlines():
            stripped = line.strip().lower()
            if stripped.startswith("user-agent:") and "*" in stripped:
                in_wildcard = True
            elif stripped.startswith("user-agent:"):
                in_wildcard = False
            elif in_wildcard and stripped.startswith("disallow:"):
                path = stripped.split(":", 1)[1].strip()
                if path:
                    disallowed.add(path)
        return disallowed

    def is_allowed(self, url: str) -> bool:
        """Check robots.txt compliance for a URL.

        Returns False if the URL path is disallowed by robots.txt.
        Returns True if robots.txt is unavailable or the path is allowed.
        Cache is per-domain for the lifetime of the CrawlerClient.
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        path = parsed.path or "/"

        # Check cache
        if domain in self._robots_cache:
            disallowed = self._robots_cache[domain]
        else:
            robots_url = f"{parsed.scheme}://{domain}/robots.txt"
            try:
                resp = self.fetch_static(robots_url)
                if resp is None or resp.status != 200:
                    # Can't fetch robots.txt → assume allowed
                    self._robots_cache[domain] = set()
                    return True
                disallowed = self._parse_robots(resp.text)
                self._robots_cache[domain] = disallowed
            except (OSError, TimeoutError, ValueError):
                self._robots_cache[domain] = set()
                return True

        # Check if path matches any disallowed prefix
        for rule in disallowed:
            if path.startswith(rule):
                logger.info("robots_disallowed", url=url, rule=rule)
                return False
        return True

    # ── Cleanup ───────────────────────────────────────────────

    def close(self):
        """Release HTTP resources and any cached connections."""
        if self._dynamic is not None:
            # DynamicFetcher sessions are per-request; no persistent browser.
            self._dynamic = None
        if self._http is not None:
            self._http = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ── Fetch methods ────────────────────────────────────────

    def fetch_static(self, url: str) -> Response | None:
        """Fetch a page using static Fetcher, with rate limiting + backoff.

        Retries on network errors and HTTP 429/503.
        Returns None if all retries are exhausted.
        """
        self._wait_if_needed()

        headers = {"User-Agent": random_user_agent()}

        for attempt in range(self._max_retries + 1):
            try:
                resp = self.http.static.get(url, headers=headers)
            except (OSError, TimeoutError):
                if attempt < self._max_retries:
                    backoff = self._backoff_base_ms * (2 ** attempt) / 1000
                    logger.debug(
                        "fetch_retry", url=url, attempt=attempt + 1,
                        backoff_s=backoff,
                    )
                    time.sleep(backoff)
                continue

            # HTTP-level retry for rate-limiting / server overload
            if resp.status not in _RETRYABLE_STATUSES or attempt >= self._max_retries:
                return resp

            retry_after = _parse_retry_after(resp)
            backoff = retry_after or self._backoff_base_ms * (2 ** attempt) / 1000
            logger.debug(
                "fetch_retry_http", url=url, status=resp.status,
                attempt=attempt + 1, backoff_s=backoff,
            )
            time.sleep(backoff)

        logger.error("fetch_static_exhausted", url=url, retries=self._max_retries)
        return None

    def fetch_dynamic(
        self,
        url: str,
        *,
        wait_selector: str | None = None,
        disable_resources: bool = True,
        block_ads: bool = True,
        headless: bool = True,
        cookies: list[dict] | None = None,
        **kwargs,
    ) -> Response | None:
        """Fetch using DynamicFetcher, with rate limiting + backoff.

        If *cookies* is provided, each cookie dict should have
        ``name``, ``value``, and ``domain`` keys (Playwright format).
        Cookies are injected before page navigation.

        Returns None if DynamicFetcher is unavailable or all retries are exhausted.
        """
        self._wait_if_needed()

        df = self.dynamic
        if df is None:
            logger.error("dynamic_fetcher_unavailable_for_url", url=url)
            return None

        page_setup = _make_page_setup(cookies)

        for attempt in range(self._max_retries + 1):
            try:
                fetch_kwargs = dict(
                    timeout=self._timeout_ms,
                    useragent=random_user_agent(),
                    headless=headless,
                    page_setup=page_setup,
                    disable_resources=disable_resources,
                    block_ads=block_ads,
                    wait_selector=wait_selector,
                    **kwargs,
                )
                if self._proxy:
                    fetch_kwargs["proxy"] = self._proxy
                resp = df.fetch(url, **fetch_kwargs)
            except (OSError, TimeoutError):
                if attempt < self._max_retries:
                    backoff = self._backoff_base_ms * (2 ** attempt) / 1000
                    logger.debug(
                        "fetch_dynamic_retry", url=url,
                        attempt=attempt + 1, backoff_s=backoff,
                    )
                    time.sleep(backoff)
                continue

            # HTTP-level retry for rate-limiting / server overload
            if resp.status not in _RETRYABLE_STATUSES or attempt >= self._max_retries:
                return resp

            retry_after = _parse_retry_after(resp)
            backoff = retry_after or self._backoff_base_ms * (2 ** attempt) / 1000
            logger.debug(
                "fetch_dynamic_retry_http", url=url, status=resp.status,
                attempt=attempt + 1, backoff_s=backoff,
            )
            time.sleep(backoff)

        logger.error("fetch_dynamic_exhausted", url=url, retries=self._max_retries)
        return None
