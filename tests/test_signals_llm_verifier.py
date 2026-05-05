"""Tests for signals/llm_verifier.py — multi-provider LLM verification."""

from unittest.mock import MagicMock, patch

import pytest

from clawithme.crawler.base import Profile
from clawithme.signals.llm_verifier import (
    LLMProvider,
    LLMVerifier,
    _call_provider,
    _parse_structured_response,
    discover_providers,
)


def _profile(site_id: str, **kw) -> Profile:
    defaults = dict(
        site_name=site_id,
        url=f"https://{site_id}.com/user",
        username=site_id,
    )
    defaults.update(kw)
    return Profile(site_id=site_id, **defaults)


def _make_provider(name="deepseek", api_key="sk-test", priority=0) -> LLMProvider:
    return LLMProvider(
        name=name,
        api_key=api_key,
        base_url="https://api.example.com/v1",
        model="test-model",
        priority=priority,
    )


# ── Provider discovery ────────────────────────────────────────

class TestDiscoverProviders:
    def test_no_env_vars_returns_empty(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        providers = discover_providers()
        assert len(providers) == 0

    def test_deepseek_discovered(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-123")
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
        providers = discover_providers()
        assert len(providers) == 1
        assert providers[0].name == "deepseek"

    def test_priority_order(self, monkeypatch):
        """DeepSeek (0) should come before DashScope (2)."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-123")
        monkeypatch.setenv("DASHSCOPE_API_KEY", "sk-dash-456")
        monkeypatch.delenv("KIMI_API_KEY", raising=False)
        providers = discover_providers()
        assert len(providers) == 2
        assert providers[0].name == "deepseek"
        assert providers[1].name == "dashscope"


# ── LLMVerifier ────────────────────────────────────────────────

class TestLLMVerifier:
    def test_is_configured_empty_providers(self):
        v = LLMVerifier(providers=[])
        assert v.is_configured() is False

    def test_is_configured_with_provider(self):
        v = LLMVerifier(providers=[_make_provider()])
        assert v.is_configured() is True

    def test_is_configured_empty_key(self):
        v = LLMVerifier(providers=[_make_provider(api_key="")])
        assert v.is_configured() is False

    def test_from_providers_factory(self):
        p = _make_provider()
        v = LLMVerifier.from_providers([p])
        assert v.is_configured() is True

    def test_verify_same_person_no_providers(self):
        v = LLMVerifier(providers=[])
        a = _profile("github", display_name="Alice")
        b = _profile("twitter", display_name="Alice")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is False
        assert conf == 0.0
        assert reason == "llm_unavailable"

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_verify_same_person_provider_failure(self, mock_call):
        mock_call.return_value = None
        p = _make_provider()
        v = LLMVerifier(providers=[p])
        a = _profile("github")
        b = _profile("twitter")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is False
        assert conf == 0.0

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_verify_same_person_same_structured(self, mock_call):
        """Structured SAME|85|reason format."""
        mock_call.return_value = "SAME|85|Same display name and location"
        v = LLMVerifier(providers=[_make_provider()])
        a = _profile("github", display_name="Alice", location="San Francisco")
        b = _profile("twitter", display_name="Alice", location="San Francisco")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is True
        assert conf == 0.85
        assert "display name" in reason

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_verify_same_person_different_structured(self, mock_call):
        mock_call.return_value = "DIFFERENT|90|Completely different bios"
        v = LLMVerifier(providers=[_make_provider()])
        a = _profile("github", display_name="John Smith", location="New York")
        b = _profile("twitter", display_name="张伟", location="Beijing")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is False
        assert conf == 0.90

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_verify_same_person_low_confidence_rejected(self, mock_call):
        """Confidence < 0.60 should be treated as uncertain."""
        mock_call.return_value = "SAME|55|Maybe same person, not sure"
        v = LLMVerifier(providers=[_make_provider()])
        a = _profile("github")
        b = _profile("twitter")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is False
        assert conf == 0.0  # rejected due to low confidence

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_verify_same_person_bare_keyword(self, mock_call):
        """Bare 'SAME' without structured format → works but lower confidence."""
        mock_call.return_value = "SAME: Both use the same profile picture"
        v = LLMVerifier(providers=[_make_provider()])
        a = _profile("github", display_name="Alice")
        b = _profile("twitter", display_name="Alice")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is True
        assert conf == 0.6  # fallback confidence

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_multi_provider_fallback(self, mock_call):
        """First provider fails, second succeeds."""
        mock_call.side_effect = [
            None,  # deepseek fails
            "SAME|80|Same person based on display name",  # kimi succeeds
        ]
        deepseek = _make_provider("deepseek", "sk-ds", priority=0)
        kimi = _make_provider("kimi", "sk-kimi", priority=1)
        v = LLMVerifier(providers=[deepseek, kimi])
        a = _profile("github", display_name="Alice")
        b = _profile("twitter", display_name="Alice")
        is_same, conf, reason = v.verify_same_person(a, b)
        assert is_same is True
        assert conf == 0.80

    def test_compose_identity_summary_no_providers(self):
        v = LLMVerifier(providers=[])
        profiles = [_profile("github", display_name="Alice")]
        summary = v.compose_identity_summary(profiles, "alice")
        assert "alice" in summary
        assert "github" in summary

    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_compose_identity_summary_success(self, mock_call):
        mock_call.return_value = (
            "Alice is a software engineer based in SF, "
            "active on GitHub and Twitter."
        )
        v = LLMVerifier(providers=[_make_provider()])
        profiles = [
            _profile("github", display_name="Alice", location="San Francisco"),
            _profile("twitter", display_name="Alice"),
        ]
        summary = v.compose_identity_summary(profiles, "alice")
        assert "Alice" in summary
        assert "software" in summary

    def test_compose_identity_summary_empty_profiles(self):
        v = LLMVerifier(providers=[_make_provider()])
        summary = v.compose_identity_summary([], "alice")
        assert "No profiles" in summary


# ── Structured response parser ─────────────────────────────────

class TestParseStructuredResponse:
    def test_same_with_score(self):
        is_same, conf, reason = _parse_structured_response(
            "SAME|85|Same display name and matching location"
        )
        assert is_same is True
        assert conf == 0.85
        assert "display name" in reason

    def test_different_with_score(self):
        is_same, conf, reason = _parse_structured_response(
            "DIFFERENT|90|Completely different bios and countries"
        )
        assert is_same is False
        assert conf == 0.90

    def test_bare_same_keyword(self):
        is_same, conf, reason = _parse_structured_response(
            "SAME: Both profiles match"
        )
        assert is_same is True
        assert conf == 0.6

    def test_bare_different_keyword(self):
        is_same, conf, reason = _parse_structured_response(
            "DIFFERENT: No overlap in any field"
        )
        assert is_same is False
        assert conf == 0.6

    def test_unparseable(self):
        is_same, conf, reason = _parse_structured_response(
            "MAYBE: Could be the same person, not sure"
        )
        assert is_same is False
        assert conf == 0.0
        assert "unparseable" in reason

    def test_score_clamped(self):
        """Score > 1.0 should be clamped."""
        is_same, conf, reason = _parse_structured_response(
            "SAME|150|Over-enthusiastic score"
        )
        assert conf == 1.0

    def test_score_negative_clamped(self):
        """Negative score should be clamped to 0."""
        is_same, conf, reason = _parse_structured_response(
            "DIFFERENT|-10|Negative score"
        )
        assert conf == 0.0

    def test_two_parts_no_reason(self):
        """SAME|75 with no reason part → reason is empty."""
        is_same, conf, reason = _parse_structured_response("SAME|75")
        assert is_same is True
        assert conf == 0.75
        assert reason == ""


# ── Benchmark ──────────────────────────────────────────────────

class TestBenchmark:
    @patch("clawithme.signals.llm_verifier._call_provider")
    def test_benchmark_pair(self, mock_call):
        """benchmark_pair runs all configured providers and returns results."""
        mock_call.side_effect = [
            "SAME|85|DeepSeek: matching names",
            "SAME|70|Kimi: likely same",
        ]
        deepseek = _make_provider("deepseek", "sk-ds", priority=0)
        kimi = _make_provider("kimi", "sk-kimi", priority=1)
        v = LLMVerifier(providers=[deepseek, kimi])
        a = _profile("github", display_name="Alice")
        b = _profile("twitter", display_name="Alice")
        results = v.benchmark_pair(a, b)
        assert len(results) == 2
        assert results[0]["provider"] == "deepseek"
        assert results[0]["confidence"] == 0.85
        assert results[1]["provider"] == "kimi"
        assert results[1]["confidence"] == 0.70


# ── Legacy backward compat ─────────────────────────────────────

class TestFallbackSummary:
    def test_no_profiles(self):
        result = LLMVerifier._fallback_summary([], "alice")
        assert result == "No profiles found for alice."

    def test_single_profile(self):
        profiles = [_profile("github")]
        result = LLMVerifier._fallback_summary(profiles, "alice")
        assert "github" in result
        assert "alice" in result

    def test_with_display_name_and_location(self):
        profiles = [_profile("github", display_name="Alice", location="SF")]
        result = LLMVerifier._fallback_summary(profiles, "alice")
        assert "github" in result
        assert "Alice" in result
        assert "SF" in result

    def test_multiple_profiles(self):
        profiles = [
            _profile("github", display_name="Alice"),
            _profile("twitter", display_name="Alice"),
        ]
        result = LLMVerifier._fallback_summary(profiles, "alice")
        assert "github" in result
        assert "twitter" in result
