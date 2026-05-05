"""LLM-based identity verification for ambiguous profile pairs.

Provider-agnostic architecture: supports any OpenAI-compatible API.
Auto-discovers providers from env vars (DEEPSEEK / KIMI / DASHSCOPE).
Tries providers in priority order with graceful fallback.

Structured output format: SAME|0.85|Brief reason in English
  - Score is 0.0–1.0 confidence (0.5 = uncertain, discard)
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass

from clawithme.crawler.base import Profile
from clawithme.logging import get_logger

logger = get_logger()

# ── Provider registry ──────────────────────────────────────────


@dataclass
class LLMProvider:
    """An OpenAI-compatible LLM API endpoint."""

    name: str
    api_key: str
    base_url: str
    model: str
    priority: int = 0  # lower = tried first

    def is_configured(self) -> bool:
        return bool(self.api_key)


def discover_providers() -> list[LLMProvider]:
    """Auto-discover providers from environment variables.

    Priority: DeepSeek (0) > Kimi (1) > 百炼/DashScope (2)
    """
    providers: list[LLMProvider] = []

    # DeepSeek V4
    ds_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if ds_key:
        providers.append(LLMProvider(
            name="deepseek",
            api_key=ds_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            model="deepseek-chat",
            priority=0,
        ))

    # Kimi / Moonshot
    kimi_key = os.environ.get("KIMI_API_KEY", "")
    if kimi_key:
        providers.append(LLMProvider(
            name="kimi",
            api_key=kimi_key,
            base_url=os.environ.get(
                "KIMI_BASE_URL", "https://api.moonshot.cn/v1"
            ),
            model="moonshot-v1-8k",
            priority=1,
        ))

    # 百炼 Coding Plan (DashScope)
    dash_key = os.environ.get("DASHSCOPE_API_KEY", "")
    if dash_key:
        providers.append(LLMProvider(
            name="dashscope",
            api_key=dash_key,
            base_url=os.environ.get(
                "DASHSCOPE_BASE_URL",
                "https://coding.dashscope.aliyuncs.com/v1",
            ),
            model="qwen-plus",
            priority=2,
        ))

    # Sort by priority
    providers.sort(key=lambda p: p.priority)
    return providers


# ── Low-level API call ─────────────────────────────────────────


def _call_provider(
    provider: LLMProvider,
    messages: list[dict[str, str]],
    max_tokens: int = 128,
) -> str | None:
    """Call a single provider. Returns content or None on failure."""
    url = f"{provider.base_url}/chat/completions"
    body = json.dumps({
        "model": provider.model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.0,
    }).encode()

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {provider.api_key}")

    try:
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        logger.warning(
            "llm_provider_failed",
            provider=provider.name,
            error=str(e)[:120],
        )
        return None


# ── Structured response parser ─────────────────────────────────


def _parse_structured_response(text: str) -> tuple[bool, float, str]:
    """Parse LLM response in SAME|score|reason format.

    Returns (is_same, confidence, reason).
    Falls back to keyword matching for bare SAME/DIFFERENT responses.
    """
    text = text.strip()

    # ── Structured format: "SAME|0.85|reason" ──
    if "|" in text:
        parts = text.split("|", 2)
        verdict = parts[0].strip().upper()
        try:
            score = float(parts[1].strip()) / 100.0 if len(parts) > 1 else 0.0
            score = max(0.0, min(1.0, score))
        except (ValueError, IndexError):
            score = 0.5
        reason = parts[2].strip() if len(parts) > 2 else ""
        if verdict.startswith("SAME"):
            return True, score, reason
        elif verdict.startswith("DIFFERENT"):
            return False, score, reason

    # ── Fallback: bare keyword matching ──
    upper = text.upper()
    if upper.startswith("SAME"):
        return True, 0.6, text
    if upper.startswith("DIFFERENT"):
        return False, 0.6, text

    # ── Unparseable ──
    return False, 0.0, f"unparseable: {text[:100]}"


# ── Verifier ───────────────────────────────────────────────────


class LLMVerifier:
    """LLM-based identity verification with multi-provider fallback.

    Usage::

        verifier = LLMVerifier()          # auto-discover from env
        verifier = LLMVerifier.from_providers([deepseek, kimi])

        is_same, confidence, reason = verifier.verify_same_person(a, b)
        if confidence >= 0.7:
            print(f"✅ Same person ({reason})")
    """

    CONFIDENCE_THRESHOLD = 0.60  # below this = uncertain, discard

    def __init__(
        self,
        providers: list[LLMProvider] | None = None,
    ) -> None:
        self._providers = providers or discover_providers()
        # Sort by priority on init
        self._providers.sort(key=lambda p: p.priority)

    @classmethod
    def from_providers(cls, providers: list[LLMProvider]) -> LLMVerifier:
        """Explicit constructor (useful for testing)."""
        return cls(providers=providers)

    @property
    def providers(self) -> list[LLMProvider]:
        return self._providers

    def is_configured(self) -> bool:
        """Check if ANY provider has a usable API key."""
        return any(p.is_configured() for p in self._providers)

    def configured_providers(self) -> list[LLMProvider]:
        """Return only providers with keys configured."""
        return [p for p in self._providers if p.is_configured()]

    def verify_same_person(
        self, profile_a: Profile, profile_b: Profile,
    ) -> tuple[bool, float, str]:
        """Ask LLM if two profiles belong to the same person.

        Returns (is_same, confidence, reasoning).
        Confidence < CONFIDENCE_THRESHOLD → treat as uncertain.
        Falls back to (False, 0.0, "llm_unavailable") if all providers fail.
        """
        providers = self.configured_providers()
        if not providers:
            return False, 0.0, "llm_unavailable"

        prompt = self._build_pair_prompt(profile_a, profile_b)

        # Try providers in priority order
        last_reason = "llm_unavailable"
        for provider in providers:
            result = _call_provider(
                provider,
                [{"role": "user", "content": prompt}],
                max_tokens=128,
            )
            if result is None:
                continue

            is_same, confidence, reason = _parse_structured_response(result)
            if confidence >= self.CONFIDENCE_THRESHOLD:
                return is_same, confidence, reason
            # Low confidence — try next provider
            last_reason = f"{provider.name}:{reason[:80]}"

        # All providers failed or low confidence
        return False, 0.0, last_reason

    def benchmark_pair(
        self, profile_a: Profile, profile_b: Profile,
    ) -> list[dict]:
        """Run ALL configured providers on a pair. Returns results for comparison.

        Returns list of dicts: [{provider, is_same, confidence, reason, latency_ms}]
        """
        results: list[dict] = []
        prompt = self._build_pair_prompt(profile_a, profile_b)

        for provider in self.configured_providers():
            t0 = time.monotonic()
            result = _call_provider(
                provider,
                [{"role": "user", "content": prompt}],
                max_tokens=128,
            )
            latency = int((time.monotonic() - t0) * 1000)

            if result:
                is_same, confidence, reason = _parse_structured_response(result)
            else:
                is_same, confidence, reason = False, 0.0, "API_FAILED"

            results.append({
                "provider": provider.name,
                "model": provider.model,
                "is_same": is_same,
                "confidence": confidence,
                "reason": reason[:120],
                "latency_ms": latency,
            })

        return results

    def compose_identity_summary(
        self, profiles: list[Profile], username: str,
    ) -> str:
        """Generate a natural language identity summary via LLM.

        Falls back to template if no provider is available.
        """
        if not profiles:
            return self._fallback_summary([], username)

        providers = self.configured_providers()
        if not providers:
            return self._fallback_summary(profiles, username)

        prompt = self._build_summary_prompt(profiles, username)

        for provider in providers:
            result = _call_provider(
                provider,
                [{"role": "user", "content": prompt}],
                max_tokens=256,
            )
            if result:
                return result.strip()

        return self._fallback_summary(profiles, username)

    # ── Prompt builders ──────────────────────────────────────

    @staticmethod
    def _build_pair_prompt(a: Profile, b: Profile) -> str:
        """Build the verification prompt for two profiles."""

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

        return (
            "You are an identity verification assistant. Given two social media "
            "profiles, determine if they likely belong to the SAME person. "
            "Consider: display name similarity, bio content, location "
            "consistency, and context.\n\n"
            "Profile A:\n" + _describe(a) + "\n\n"
            "Profile B:\n" + _describe(b) + "\n\n"
            "Reply in this format: SAME|score|reason  OR  DIFFERENT|score|reason\n"
            "Score is 0-100 confidence (85 = very confident, 50 = guessing).\n"
            "Reason is one short sentence in English.\n"
            "Example: SAME|90|Same display name, matching bio and location"
        )

    @staticmethod
    def _build_summary_prompt(profiles: list[Profile], username: str) -> str:
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

        return (
            "You are an identity profiler. Given social media profiles for "
            f"username {username}, write a 2-3 sentence natural language "
            "identity summary. Include: who they appear to be "
            "(role/profession), where they are based, and which platforms "
            "they are active on.\n\n"
            f"Profiles:\n{profile_lines}\n\nSummary:"
        )

    @staticmethod
    def _fallback_summary(
        profiles: list[Profile], username: str,
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
