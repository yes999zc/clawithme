"""LinkedIn profile extractor — cookie-based login + deep extraction.

Requires a LinkedIn cookie file (JSON format, exported from browser DevTools).
Without cookies, falls back to public-page best-effort extraction.

Cookie export: F12 → Application → Cookies → linkedin.com → Copy All as JSON.
Save to a file and set ``cookies.linkedin_file`` in config.toml.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.client import CrawlerClient
from clawithme.crawler.utils import first_text
from clawithme.engine.http_client import HttpResponse
from clawithme.logging import get_logger

logger = get_logger()

# ── Cookie helpers ────────────────────────────────────────────


def _load_cookies(filepath: str) -> list[dict]:
    """Load LinkedIn cookies from a JSON file.

    Expected format (Chrome DevTools export):
        [{"name":"li_at","value":"...","domain":".linkedin.com"}, ...]

    Returns Playwright-compatible cookie dicts with standardised keys.
    """
    raw = json.loads(Path(filepath).expanduser().read_text())
    cookies = []
    for c in raw:
        cookie = {}
        # Normalise various export formats
        for src, dst in [
            ("name", "name"), ("value", "value"),
            ("domain", "domain"), ("path", "path"),
            ("httpOnly", "httpOnly"), ("secure", "secure"),
            ("sameSite", "sameSite"),
        ]:
            if src in c:
                cookie[dst] = c[src]
        # Expiry: some exports use "expirationDate", others use "expires"
        if "expirationDate" in c and c["expirationDate"]:
            cookie["expires"] = c["expirationDate"]
        elif "expires" in c and c["expires"]:
            cookie["expires"] = c["expires"]
        if "name" in cookie:
            cookies.append(cookie)
    return cookies


def _fetch_playwright_page(url: str, cookies: list[dict]) -> "HttpResponse | None":
    """Fetch a LinkedIn page via Playwright with cookie auth.

    Returns engine's HttpResponse so both probe and extractor can use it.
    """
    from clawithme.engine.http_client import HttpResponse

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright_unavailable")
        return None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
            )
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
            try:
                context.add_cookies(cookies)
            except Exception:
                pass

            resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
            status = resp.status if resp else 0
            text = page.content()
            headers = dict(resp.headers) if resp and resp.headers else {}

            browser.close()
            return HttpResponse(
                status_code=status, url=page.url,
                text=text, headers=headers,
            )
    except (OSError, TimeoutError) as e:
        logger.warning("playwright_fetch_failed", url=url, error=str(e))
        return None


# ── Extraction helpers ────────────────────────────────────────


def _parse_count(text: str) -> int | None:
    """Parse follower/connection counts like '500+ connections' or '1,234 followers'."""
    if not text:
        return None
    m = re.search(r"([\d,]+)\s*\+?", text)
    if not m:
        return None
    return int(m.group(1).replace(",", ""))


def _extract_experience(page_text: str) -> list[dict]:
    """Extract work experience entries from page text."""
    entries = []
    # LinkedIn renders experience as sections with company/title/date patterns
    # Use a regex approach on the visible text
    # Look for patterns like: "Company Name\nTitle\nDate Range"
    lines = [l.strip() for l in page_text.splitlines() if l.strip()]
    # Skip known noise lines
    skip_keywords = {
        "Home", "My Network", "Jobs", "Messaging", "Notifications",
        "Me", "Search", "Sign in", "Join now", "Open to",
    }
    lines = [l for l in lines if l not in skip_keywords and len(l) > 2]
    return entries


def _extract_education(page_text: str) -> list[dict]:
    """Extract education entries from page text."""
    return []


class LinkedinExtractor(ProfileExtractor):
    """Extract LinkedIn profile with cookie-based login.

    With cookies: full profile data (name, headline, location, about,
    experience, education, skills, connections).
    Without cookies: public-page best-effort (meta tags, OG data).
    """

    site_id = "linkedin"
    requires_dynamic = True

    def extract(self, site: dict, username: str) -> Profile:
        url = f"https://www.linkedin.com/in/{quote(username)}"
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "LinkedIn"),
            url=url,
            username=username,
        )

        # ── Load cookies if configured ──
        cookies: list[dict] | None = None
        cookie_file = (
            site.get("cookie_file")
            or site.get("auth", {}).get("cookie_file", "")
            or ""
        )
        if not cookie_file:
            try:
                from clawithme.config import load_config
                cookie_file = load_config().apis.linkedin_cookie_file
            except Exception:
                pass
        if cookie_file:
            try:
                cookies = _load_cookies(cookie_file)
                logger.info("linkedin_cookies_loaded", count=len(cookies))
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.warning("linkedin_cookies_load_failed", error=str(e))

        try:
            if cookies:
                response = _fetch_playwright_page(url, cookies)
                if response is not None and response.status_code == 200:
                    profile = self._extract_authenticated(response, profile, username)
                else:
                    logger.warning("linkedin_dynamic_failed",
                                  status=response.status_code if response else None)
            else:
                # Fallback: static fetch without cookies (public page)
                logger.info("linkedin_no_cookies", username=username)
                client = CrawlerClient(timeout_ms=20000, proxy=site.get("proxy"))
                try:
                    response = client.fetch_static(url)
                    if response is not None and response.status == 200:
                        profile = self._extract_public(response, profile)
                finally:
                    client.close()
        except (OSError, TimeoutError) as e:
            logger.warning("linkedin_fetch_failed", error=str(e))

        return profile

    def _extract_authenticated(self, response: HttpResponse, profile: Profile, username: str) -> Profile:
        """Full profile extraction with logged-in page."""
        page_text = response.text or ""
        if not page_text and response.body:
            try:
                page_text = response.body.decode("utf-8", errors="replace")
            except Exception:
                page_text = str(response.body)

        if not page_text:
            return profile

        clean = re.sub(r"\s+", " ", page_text)

        # ── Name (try multiple sources) ──
        # <title> tag
        title_m = re.search(r"<title>([^|]+)\s*\|", clean)
        if title_m:
            title_name = title_m.group(1).strip()
            if title_name and "LinkedIn" not in title_name:
                profile.display_name = title_name

        # OG title
        if not profile.display_name:
            og_m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', clean)
            if og_m:
                profile.display_name = og_m.group(1).strip()

        # JSON-LD
        if not profile.display_name:
            jsonld_m = re.search(
                r'<script type="application/ld\+json">(.*?)</script>', clean, re.DOTALL
            )
            if jsonld_m:
                try:
                    ld = json.loads(jsonld_m.group(1))
                    if isinstance(ld, dict):
                        profile.display_name = ld.get("name", "")
                        if ld.get("description") and not profile.bio:
                            profile.bio = ld["description"][:500]
                except (json.JSONDecodeError, TypeError):
                    pass

        # h1 fallback
        if not profile.display_name:
            name_m = re.search(r"<h1[^>]*>([^<]+)</h1>", clean)
            if name_m:
                profile.display_name = name_m.group(1).strip()

        # ── Visible text extraction ──
        # Strip all HTML tags to get plain text, then parse sections
        plain = re.sub(r"<script[^>]*>.*?</script>", " ", page_text, flags=re.DOTALL)
        plain = re.sub(r"<style[^>]*>.*?</style>", " ", plain, flags=re.DOTALL)
        plain = re.sub(r"<[^>]+>", " ", plain)
        plain = re.sub(r"&nbsp;", " ", plain)
        plain = re.sub(r"\s+", " ", plain).strip()

        lines = [l.strip() for l in plain.splitlines() if l.strip()]
        meaningful = [l for l in lines if len(l) > 3 and not l.startswith("{") and not l.startswith("/*")]

        # ── Connection count ──
        for line in meaningful:
            if "followers" in line.lower() or "connections" in line.lower():
                count = _parse_count(line)
                if count:
                    if "follower" in line.lower():
                        profile.follower_count = profile.follower_count or count
                    else:
                        profile.following_count = profile.following_count or count
                    break

        # ── Structured extra ──
        extra: dict = {}

        # Scan meaningful text for recognizable sections
        section_keywords = {
            "experience": ["experience", "经历", "工作经历"],
            "education": ["education", "教育经历", "教育"],
            "skills": ["skills", "技能", "endorsements"],
            "about": ["about", "关于"],
        }

        for i, line in enumerate(meaningful):
            line_lower = line.lower()
            for section, keywords in section_keywords.items():
                if any(kw in line_lower for kw in keywords):
                    # Collect subsequent lines until next section or empty
                    items = []
                    for j in range(i + 1, min(i + 50, len(meaningful))):
                        next_line = meaningful[j].strip()
                        if len(next_line) < 3:
                            break
                        if any(
                            any(kw in next_line.lower() for kw in sec_kws)
                            for sec_kws in section_keywords.values()
                        ):
                            break
                        items.append(next_line)
                    if items:
                        key_map = {
                            "experience": "experience_items",
                            "education": "education_items",
                            "skills": "skills",
                            "about": "about_text",
                        }
                        extra[key_map[section]] = items[:30]

        if extra:
            profile.extra = extra

        logger.debug(
            "linkedin_authenticated_extracted",
            username=username,
            display_name=profile.display_name,
            headline=bool(profile.bio),
            extra_keys=list(extra.keys()),
        )

        return profile

    def _extract_public(self, response, profile: Profile) -> Profile:
        """Best-effort extraction from public (non-logged-in) page."""
        page_text = getattr(response, "text", "") or ""

        # Login wall — bail out early
        if "login" in page_text[:2000].lower() or "Sign in" in page_text[:2000]:
            return profile

        # JSON-LD
        for script in response.css("script[type=\"application/ld+json\"]"):
            try:
                data = json.loads(script.text)
                if isinstance(data, dict):
                    profile.display_name = data.get("name", profile.display_name)
                    profile.bio = data.get("description", profile.bio)
            except (json.JSONDecodeError, AttributeError, TypeError):
                continue

        # CSS fallbacks
        name = first_text(response, [
            "h1", "meta[property=\"og:title\"]",
            ".text-heading-xlarge",
        ])
        if name:
            profile.display_name = name

        headline = first_text(response, [
            ".text-body-medium", "meta[name=\"description\"]",
        ])
        if headline:
            profile.bio = headline

        location = first_text(response, ["[class*=\"location\"]"])
        if location:
            profile.location = location

        for sel in ["img[class*=\"profile-photo\"]", "img[class*=\"avatar\"]"]:
            imgs = response.css(sel)
            if imgs:
                src = imgs[0].attrib.get("src", "")
                if src and not src.startswith("data:"):
                    profile.avatar_url = src
                    break

        logger.debug("linkedin_public_extracted", display_name=profile.display_name)
        return profile
