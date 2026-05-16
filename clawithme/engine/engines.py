"""Engine runner — executes detection logic defined in engines.json.

Key design decisions:
- Template variables use manual dict replacement (no Jinja2) for sandbox safety.
- Variable whitelist: only {username}, {e_code}, {e_string}, {m_string},
  {e_headers}, {probe_url}, {url_subpath} are allowed.
- Detection type (status_code / message / headers) is determined by
  engine.classifier — sites never declare their own type.
- Cookie auth: sites with ``auth.type == "cookie"`` use cookie-based
  Playwright fetch for the probe phase (e.g. LinkedIn).
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from clawithme.engine.http_client import HttpClient, HttpResponse
from clawithme.logging import get_logger

logger = get_logger()

# DynamicFetcher availability (lazy, cached)
_DYNAMIC_AVAILABLE: bool | None = None


def _check_dynamic() -> bool:
    global _DYNAMIC_AVAILABLE
    if _DYNAMIC_AVAILABLE is None:
        try:
            from scrapling import DynamicFetcher  # noqa: F401
            _DYNAMIC_AVAILABLE = True
        except ImportError:
            _DYNAMIC_AVAILABLE = False
    return _DYNAMIC_AVAILABLE

def _load_cookie_file(filepath: str) -> list[dict] | None:
    """Load cookies from a JSON file. Returns None on failure."""
    try:
        raw = json.loads(Path(filepath).expanduser().read_text())
        cookies = []
        for c in raw:
            cookie = {}
            for src, dst in [
                ("name", "name"), ("value", "value"),
                ("domain", "domain"), ("path", "path"),
                ("httpOnly", "httpOnly"), ("secure", "secure"),
                ("sameSite", "sameSite"),
            ]:
                if src in c:
                    cookie[dst] = c[src]
            if "expirationDate" in c and c["expirationDate"]:
                cookie["expires"] = c["expirationDate"]
            if "name" in cookie:
                cookies.append(cookie)
        return cookies if cookies else None
    except (OSError, json.JSONDecodeError, ValueError):
        return None


# Allowed template variables (whitelist) — enforced in _substitute()
_ALLOWED_VARS = {
    "{username}", "{e_code}", "{e_string}", "{m_string}",
    "{probe_url}", "{url_subpath}",
}


@dataclass
class EngineResult:
    """Result of a single site probe."""

    site_id: str
    site_name: str
    url_probed: str
    status_code: int
    exists: bool
    engine: str
    classifier: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class Engine:
    """Detection engine — knows 'how to check', receives 'what to check'.

    Accepts an optional *proxy_manager* for per-tier proxy selection.
    Falls back to *http_client* (or a plain HttpClient) if no proxy_manager.
    """

    def __init__(
        self,
        engine_def: dict,
        http_client: HttpClient | None = None,
        proxy_manager: "ProxyManager | None" = None,
    ):
        from clawithme.engine.proxy_manager import ProxyManager

        self._def = engine_def
        self._http = http_client or HttpClient()
        self._proxy_manager: ProxyManager | None = proxy_manager
        self._dynamic = None  # DynamicFetcher, lazy
        self._log = get_logger(engine=engine_def.get("name", "?"))

    @property
    def name(self) -> str:
        return self._def.get("name", "?")

    @property
    def classifier(self) -> str:
        """Detection type: status_code | message | headers."""
        return self._def["classifier"]

    @property
    def params(self) -> dict:
        return self._def.get("params", {})

    @property
    def dynamic(self):
        """Lazy-init DynamicFetcher for JS-rendered pages."""
        if not _check_dynamic():
            return None
        if self._dynamic is None:
            from scrapling import DynamicFetcher
            self._dynamic = DynamicFetcher()
        return self._dynamic

    def _fetch_dynamic(
        self, url: str, cookies: list[dict] | None = None
    ) -> HttpResponse | None:
        """Fetch a page using Playwright-based DynamicFetcher.

        If *cookies* is provided, they are injected before navigation.
        Falls back to direct Playwright if Scrapling's DynamicFetcher
        is unavailable (common on some installations).

        Returns HttpResponse or None on failure.
        """
        # Prefer Scrapling's DynamicFetcher if available
        df = self.dynamic
        if df is not None and not cookies:
            try:
                page = df.fetch(
                    url, timeout=15000, headless=True,
                    disable_resources=True, block_ads=True,
                )
                body = page.body if page.body else b""
                text = str(page.html_content) if page.html_content else ""
                if not text and body:
                    text = body.decode("utf-8", errors="replace")
                return HttpResponse(
                    status_code=page.status, url=str(page.url),
                    text=text, headers=dict(page.headers) if page.headers else {},
                    body=body,
                )
            except (OSError, TimeoutError) as e:
                self._log.warning("dynamic_fetch_failed", url=url, error=str(e))
                return None

        # Cookie-based or DynamicFetcher unavailable — use Playwright directly
        if cookies or df is None:
            return self._fetch_playwright(url, cookies)

        return None

    def _fetch_playwright(
        self, url: str, cookies: list[dict] | None = None
    ) -> HttpResponse | None:
        """Fetch via Playwright directly (bypasses Scrapling)."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._log.warning("playwright_unavailable", url=url)
            return None

        try:
            with sync_playwright() as pw:
                browser = None
                context = None
                browser = pw.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                )
                try:
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 800},
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/131.0.0.0 Safari/537.36"
                        ),
                    )
                    page = context.new_page()
                    page.add_init_script("""
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    """)
                    if cookies:
                        try:
                            context.add_cookies(cookies)
                        except Exception:
                            pass

                    resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    status = resp.status if resp else 0
                    text = page.content()
                    headers = {}
                    if resp:
                        headers = dict(resp.headers) if resp.headers else {}

                    return HttpResponse(
                        status_code=status, url=page.url,
                        text=text, headers=headers,
                    )
                finally:
                    if context is not None:
                        with suppress(Exception):
                            context.close()
                    if browser is not None:
                        with suppress(Exception):
                            browser.close()
        except (OSError, TimeoutError) as e:
            self._log.warning("playwright_fetch_failed", url=url, error=str(e))
            return None

    def probe(self, site: dict, username: str) -> EngineResult:
        """Probe a site for a given username.

        Uses DynamicFetcher (Playwright) for sites with dynamic_fetch: true.
        Falls back to static HttpClient otherwise.

        Timeout priority: site check.timeout_ms > engine params.timeout_ms
        (previously both were ignored — HttpClient always used 5000ms).
        """
        check = site.get("check", {})
        probe_template = check.get("probe_url", site.get("canonical_url", ""))
        url = self._substitute(probe_template, check, username)
        use_dynamic = check.get("dynamic_fetch", False)

        # Resolve timeout: site → engine → HttpClient default
        timeout_ms = check.get("timeout_ms") or self.params.get("timeout_ms")

        # Cookie-based auth (e.g. LinkedIn) — force Playwright with cookies
        cookie_auth = site.get("auth", {})
        use_cookies = cookie_auth.get("type") == "cookie"
        cookies: list[dict] | None = None
        if use_cookies:
            cookie_file = cookie_auth.get("cookie_file", "")
            if cookie_file:
                cookies = _load_cookie_file(cookie_file)
                use_dynamic = True  # cookie auth requires a browser

        try:
            if use_dynamic:
                resp = self._fetch_dynamic(url, cookies=cookies)
                if resp is None:
                    return EngineResult(
                        site_id=site["id"],
                        site_name=site["name"],
                        url_probed=url,
                        status_code=0,
                        exists=False,
                        engine=self.name,
                        classifier=self.classifier,
                        error="dynamic_fetch_failed",
                    )
            else:
                # Select client by site's proxy_tier (falls back to self._http)
                client = self._http
                if self._proxy_manager is not None:
                    client = self._proxy_manager.get_client(
                        site.get("proxy_tier")
                    )
                resp = client.get(url, headers=check.get("headers"),
                                  timeout_ms=timeout_ms)

            exists = self._classify(resp, check)
            return EngineResult(
                site_id=site["id"],
                site_name=site["name"],
                url_probed=url,
                status_code=resp.status_code,
                exists=exists,
                engine=self.name,
                classifier=self.classifier,
                details={"body_len": len(resp.text) if resp.text else 0,
                         "dynamic": use_dynamic},
            )
        except (OSError, ValueError, TimeoutError) as e:
            self._log.warning("probe_failed", site_id=site["id"], error=str(e))
            return EngineResult(
                site_id=site["id"],
                site_name=site["name"],
                url_probed=url,
                status_code=0,
                exists=False,
                engine=self.name,
                classifier=self.classifier,
                error=str(e),
            )

    def _classify(self, resp: HttpResponse, check: dict) -> bool:
        """Classify response as 'account exists' or not."""
        if self.classifier == "status_code":
            expected = check.get("expected", 200)
            return resp.status_code == expected

        if self.classifier == "message":
            text = resp.text or ""
            presence = check.get("presence_strs", [])
            absence = check.get("absence_strs", [])
            if not presence and not absence:
                self._log.warning("message_classifier_no_rules",
                                 site_id=check.get("probe_url", "?"))
                return False  # conservative: no rules = no detection
            has_presence = any(s in text for s in presence) if presence else True
            has_absence = any(s in text for s in absence)
            return has_presence and not has_absence

        if self.classifier == "headers":
            expected_headers = check.get("expected_headers", {})
            return all(
                resp.headers.get(k) == v
                for k, v in expected_headers.items()
            )

        # Unknown classifier — fall back to status_code
        expected = check.get("expected", 200)
        return resp.status_code == expected

    @staticmethod
    def _substitute(template: str, check: dict, username: str) -> str:
        """Safely substitute template variables. Whitelist enforced.

        Raises ValueError if template contains unknown {variable} patterns.
        """
        # Validate: no unknown template variables
        import re
        found = set(re.findall(r"\{(\w+)\}", template))
        allowed_names = {v.strip("{}") for v in _ALLOWED_VARS}
        unknown = found - allowed_names
        if unknown:
            raise ValueError(
                f"Unknown template variable(s): {unknown}. "
                f"Allowed: {allowed_names}"
            )

        subs = {
            "{username}": username,
            "{e_code}": str(check.get("expected", 200)),
            "{e_string}": (
                str(presence[0]) if (presence := check.get("presence_strs")) else ""
            ),
            "{m_string}": (
                str(absence[0]) if (absence := check.get("absence_strs")) else ""
            ),
            "{probe_url}": check.get("probe_url", template),
            "{url_subpath}": check.get("subpath", ""),
        }
        result = template
        for var, val in subs.items():
            result = result.replace(var, val)
        return result
