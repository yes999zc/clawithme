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
        cookie_file = site.get("cookie_file", "")
        if not cookie_file:
            # Try config default
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

        client = CrawlerClient(timeout_ms=20000, proxy=site.get("proxy"))
        try:
            if cookies:
                response = client.fetch_dynamic(
                    url,
                    cookies=cookies,
                    wait_selector="h1",
                    disable_resources=False,  # LinkedIn needs images/CSS to look human
                )
                if response is not None and response.status == 200:
                    profile = self._extract_authenticated(response, profile, username)
                else:
                    logger.warning("linkedin_dynamic_failed",
                                  status=getattr(response, "status", None))
            else:
                # Fallback: static fetch without cookies (public page)
                logger.info("linkedin_no_cookies", username=username)
                response = client.fetch_static(url)
                if response is not None and response.status == 200:
                    profile = self._extract_public(response, profile)
        finally:
            client.close()

        return profile

    def _extract_authenticated(self, response, profile: Profile, username: str) -> Profile:
        """Full profile extraction with logged-in page."""
        page_text = getattr(response, "text", "") or ""
        if not page_text and hasattr(response, "html_content"):
            page_text = str(response.html_content) or ""
        if not page_text and hasattr(response, "body"):
            body = response.body
            if body:
                try:
                    page_text = body.decode("utf-8", errors="replace")
                except Exception:
                    page_text = str(body)

        if not page_text:
            return profile

        # Remove excessive whitespace for regex matching
        clean = re.sub(r"\s+", " ", page_text)

        # ── Name ──
        name_m = re.search(r'<h1[^>]*>([^<]+)</h1>', clean)
        if name_m:
            profile.display_name = name_m.group(1).strip()

        # ── Headline ──
        headline_m = re.search(
            r'(?:text-body-medium break-words[^>]*>)([^<]+)<',
            clean,
        )
        if not headline_m:
            # LinkedIn sometimes puts headline right after h1
            headline_m = re.search(
                r'</h1>\s*<[^>]*>\s*<[^>]*>\s*([^<]{5,200})<',
                clean,
            )
        if headline_m:
            headline = headline_m.group(1).strip()
            if headline and headline != profile.display_name:
                profile.bio = headline

        # ── Location ──
        loc_m = re.search(
            r'(?:text-body-small inline t-black--light[^>]*>)\s*([^<]+)<',
            clean,
        )
        if loc_m:
            profile.location = loc_m.group(1).strip()

        # ── Connection / follower count ──
        conn_m = re.search(r"([\d,]+)\s*(?:followers|connections)", clean, re.IGNORECASE)
        if conn_m:
            count = _parse_count(conn_m.group(0))
            if conn_m.group(0).lower().endswith("followers"):
                profile.follower_count = count
            else:
                profile.following_count = count

        # ── About section ──
        about_m = re.search(r'id="about"[^>]*>.*?</section>', clean, re.DOTALL)
        if about_m:
            about_text = re.sub(r"<[^>]+>", " ", about_m.group(0))
            about_text = re.sub(r"\s+", " ", about_text).strip()
            if len(about_text) > 20:
                profile.bio = (profile.bio or "") + "\n\n" + about_text

        # ── Structured extra data ──
        extra: dict = {}

        # Experience — look for section with company names
        exp_section = re.search(
            r'(?:experience|position).*?</section>', clean, re.DOTALL | re.IGNORECASE
        )
        if exp_section:
            # Extract company names
            companies = re.findall(
                r'(?:t-14 t-normal[^>]*>\s*<span[^>]*>\s*([^<]+)<)',
                exp_section.group(0),
            )
            if companies:
                extra["experience_companies"] = companies[:10]

        # Education
        edu_section = re.search(
            r'(?:education).*?</section>', clean, re.DOTALL | re.IGNORECASE
        )
        if edu_section:
            schools = re.findall(
                r'(?:t-16 t-bold[^>]*>\s*<span[^>]*>\s*([^<]+)<)',
                edu_section.group(0),
            )
            if schools:
                extra["education_schools"] = schools[:5]

        # Skills
        skills = re.findall(
            r'(?:t-16 t-black t-bold[^>]*>\s*<span[^>]*>\s*([^<]{2,40})<)',
            clean,
        )
        if skills:
            extra["skills"] = skills[:20]

        # About text
        about_match = re.search(r'"about":"([^"]+)"', clean)
        if about_match:
            extra["about"] = about_match.group(1)[:500]

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
