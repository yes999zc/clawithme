"""LLM-based identity verification for ambiguous profile pairs.

Uses DeepSeek API (OpenAI-compatible) to resolve cases where
the rule engine is uncertain. Falls back gracefully on failure.
"""

from __future__ import annotations

import json
import os
import urllib.request

from clawithme.crawler.base import Profile
from clawithme.logging import get_logger

logger = get_logger()

_DEFAULT_BASE_URL = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"


def _get_api_key() -> str:
    return os.environ.get("DEEPSEEK_API_KEY", "")


def _call_llm(
    messages: list[dict[str, str]],
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
    max_tokens: int = 256,
) -> str | None:
    """Call OpenAI-compatible chat API. Returns content or None on failure."""
    key = api_key or _get_api_key()
    if not key:
        return None

    url = f"{base_url or _DEFAULT_BASE_URL}/chat/completions"
    body = json.dumps({
        "model": model or _DEFAULT_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {key}")

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception:
        logger.exception("llm_call_failed")
        return None


class LLMVerifier:
    """LLM-based identity verification for ambiguous profile pairs."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = _DEFAULT_BASE_URL,
        model: str = _DEFAULT_MODEL,
    ):
        self.api_key = api_key or _get_api_key()
        self.base_url = base_url
        self.model = model

    @staticmethod
    def is_configured() -> bool:
        return bool(_get_api_key())

    def verify_same_person(
        self, profile_a: Profile, profile_b: Profile
    ) -> tuple[bool, str]:
        """Ask LLM if two profiles belong to the same person.

        Returns (is_same_person, reasoning_string).
        Falls back to (False, "llm_unavailable") if API call fails.
        """
        if not self.api_key:
            return False, "llm_unavailable"

        def _describe(p: Profile) -> str:
            parts = [f"Platform: {p.site_id}"]
            if p.display_name:
                parts.append(f"Display name: {p.display_name}")
            if p.bio:
                parts.append(f"Bio: {p.bio[:200]}")
            if p.location:
                parts.append(f"Location: {p.location}")
            if p.email:
                parts.append(f"Email: {p.email}")
            if p.joined_date:
                parts.append(f"Joined: {p.joined_date}")
            return "\n".join(parts)

        prompt = (
            "You are an identity verification assistant. Given two social media "
            "profiles, determine if they likely belong to the SAME person. "
            "Consider: display name similarity, bio content, location "
            "consistency, and context.\n\n"
            "Profile A:\n" + _describe(profile_a) + "\n\n"
            "Profile B:\n" + _describe(profile_b) + "\n\n"
            "Reply with ONLY one word: SAME or DIFFERENT, followed by a brief reason."
        )

        result = _call_llm(
            [{"role": "user", "content": prompt}],
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            max_tokens=128,
        )

        if result is None:
            return False, "llm_unavailable"

        result_upper = result.strip().upper()
        is_same = result_upper.startswith("SAME")
        return is_same, result.strip()

    def compose_identity_summary(
        self, profiles: list[Profile], username: str
    ) -> str:
        """Generate a natural language identity summary.

        Falls back to a simple template if API unavailable.
        """
        if not self.api_key or not profiles:
            return self._fallback_summary(profiles, username)

        def _describe(p: Profile) -> str:
            parts = [f"{p.site_id}"]
            if p.display_name:
                parts.append(f"name={p.display_name}")
            if p.bio:
                parts.append(f"bio={p.bio[:150]}")
            if p.location:
                parts.append(f"location={p.location}")
            return " ".join(parts)

        profile_lines = "\n".join(
            f"- {_describe(p)}" for p in profiles[:20]
        )

        prompt = (
            "You are an identity profiler. Given social media profiles for "
            f"username {username}, write a 2-3 sentence natural language "
            "identity summary. Include: who they appear to be "
            "(role/profession), where they are based, and which platforms "
            "they are active on.\n\n"
            f"Profiles:\n{profile_lines}\n\nSummary:"
        )

        result = _call_llm(
            [{"role": "user", "content": prompt}],
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            max_tokens=256,
        )

        if result:
            return result.strip()
        return self._fallback_summary(profiles, username)

    @staticmethod
    def _fallback_summary(
        profiles: list[Profile], username: str
    ) -> str:
        """Simple template-based summary when LLM is unavailable."""
        if not profiles:
            return f"No profiles found for {username}."
        sites = [p.site_id for p in profiles]
        names = [p.display_name for p in profiles if p.display_name]
        location = next((p.location for p in profiles if p.location), None)
        parts = [f"{username} has profiles on {', '.join(sites)}"]
        if names:
            parts.append(f"display names: {', '.join(names)}")
        if location:
            parts.append(f"based in {location}")
        return ". ".join(parts) + "."
