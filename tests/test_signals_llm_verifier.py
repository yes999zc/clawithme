"""Tests for signals/llm_verifier.py — LLM-based identity verification."""

from unittest.mock import patch

from clawithme.crawler.base import Profile
from clawithme.signals.llm_verifier import LLMVerifier, _call_llm, _get_api_key


def _profile(site_id: str, **kw) -> Profile:
    defaults = dict(
        site_name=site_id,
        url=f"https://{site_id}.com/user",
        username=site_id,
    )
    defaults.update(kw)
    return Profile(site_id=site_id, **defaults)


class TestLLMVerifier:
    def test_is_configured_false_when_no_key(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        assert LLMVerifier.is_configured() is False

    def test_is_configured_true_with_key(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test-123")
        assert LLMVerifier.is_configured() is True

    def test_verify_same_person_no_api_key(self):
        """Should fall back gracefully when no API key."""
        v = LLMVerifier(api_key="")
        a = _profile("github", display_name="Alice")
        b = _profile("twitter", display_name="Alice")
        result, reason = v.verify_same_person(a, b)
        assert result is False
        assert reason == "llm_unavailable"

    @patch("clawithme.signals.llm_verifier._call_llm")
    def test_verify_same_person_api_failure(self, mock_call):
        """Should fall back when _call_llm returns None."""
        mock_call.return_value = None
        v = LLMVerifier(api_key="sk-test-123")
        a = _profile("github")
        b = _profile("twitter")
        result, reason = v.verify_same_person(a, b)
        assert result is False
        assert reason == "llm_unavailable"

    @patch("clawithme.signals.llm_verifier._call_llm")
    def test_verify_same_person_same(self, mock_call):
        mock_call.return_value = (
            "SAME: Both profiles use 'Alice' and share location "
            "'San Francisco'."
        )
        v = LLMVerifier(api_key="sk-test-123")
        a = _profile("github", display_name="Alice", location="San Francisco")
        b = _profile("twitter", display_name="Alice", location="San Francisco")
        result, reason = v.verify_same_person(a, b)
        assert result is True
        assert "SAME" in reason

    @patch("clawithme.signals.llm_verifier._call_llm")
    def test_verify_same_person_different(self, mock_call):
        mock_call.return_value = (
            "DIFFERENT: Different display names and locations."
        )
        v = LLMVerifier(api_key="sk-test-123")
        a = _profile(
            "github", display_name="John Smith", location="New York"
        )
        b = _profile(
            "twitter", display_name="张伟", location="Beijing"
        )
        result, reason = v.verify_same_person(a, b)
        assert result is False
        assert "DIFFERENT" in reason

    @patch("clawithme.signals.llm_verifier._call_llm")
    def test_verify_same_person_unexpected_response(self, mock_call):
        """Unexpected LLM response should not crash; treated as DIFFERENT."""
        mock_call.return_value = "MAYBE: Could be same person."
        v = LLMVerifier(api_key="sk-test-123")
        a = _profile("github")
        b = _profile("twitter")
        result, reason = v.verify_same_person(a, b)
        assert result is False

    def test_compose_identity_summary_no_api_key(self):
        """Should return fallback summary when no API key."""
        v = LLMVerifier(api_key="")
        profiles = [_profile("github", display_name="Alice")]
        summary = v.compose_identity_summary(profiles, "alice")
        assert "alice" in summary
        assert "github" in summary

    def test_compose_identity_summary_empty_profiles(self):
        """Should handle empty profiles list."""
        v = LLMVerifier(api_key="sk-test-123")
        summary = v.compose_identity_summary([], "alice")
        assert "No profiles" in summary

    @patch("clawithme.signals.llm_verifier._call_llm")
    def test_compose_identity_summary_success(self, mock_call):
        mock_call.return_value = (
            "Alice is a software engineer based in SF, "
            "active on GitHub and Twitter."
        )
        v = LLMVerifier(api_key="sk-test-123")
        profiles = [
            _profile("github", display_name="Alice", location="San Francisco"),
            _profile("twitter", display_name="Alice"),
        ]
        summary = v.compose_identity_summary(profiles, "alice")
        assert "Alice" in summary
        assert "software" in summary


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
        profiles = [
            _profile("github", display_name="Alice", location="SF")
        ]
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


class TestCallLLM:
    def test_no_api_key(self):
        result = _call_llm(
            [{"role": "user", "content": "test"}], api_key=""
        )
        assert result is None

    def test_no_api_key_fallback_to_env(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        result = _call_llm([{"role": "user", "content": "test"}])
        assert result is None

    def test_get_api_key_no_env(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        assert _get_api_key() == ""

    def test_get_api_key_with_env(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-123")
        assert _get_api_key() == "sk-123"

    def test_get_api_key_deleted_then_no_key(self, monkeypatch):
        """Verify that deleting env var causes empty key."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        assert _get_api_key() == ""
