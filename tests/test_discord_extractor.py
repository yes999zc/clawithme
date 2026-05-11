"""Tests for DiscordExtractor."""

import json
from unittest.mock import MagicMock, patch

from clawithme.crawler.extractors.discord import DiscordExtractor


class TestDiscordExtractor:
    """Unit tests for Discord profile extractor."""

    def test_can_handle_discord(self) -> None:
        ex = DiscordExtractor()
        assert ex.can_handle({"id": "discord"}) is True

    def test_can_handle_other(self) -> None:
        ex = DiscordExtractor()
        assert ex.can_handle({"id": "twitter"}) is False

    def test_requires_dynamic_false(self) -> None:
        ex = DiscordExtractor()
        assert ex.requires_dynamic is False

    def test_extract_no_token_returns_empty_profile(self) -> None:
        """When DISCORD_BOT_TOKEN is not set, return empty profile."""
        ex = DiscordExtractor()
        with patch.dict("os.environ", {}, clear=True):
            profile = ex.extract(
                {"id": "discord", "name": "Discord"},
                "270904126974590976",
            )
        assert profile.site_id == "discord"
        assert profile.username == "270904126974590976"
        assert profile.empty is True

    def test_extract_with_mock_response(self) -> None:
        """Verify all Profile fields are correctly extracted from API response."""
        mock_response = {
            "id": "270904126974590976",
            "username": "testuser",
            "discriminator": "0001",
            "global_name": "Test User",
            "avatar": "abc123def456",
            "banner": "banner_hash_001",
            "accent_color": 5793266,
            "bio": "Hello, I am a test user!",
            "public_flags": 4194304,
            "avatar_decoration_data": {"asset": "a_123", "sku_id": "sku_1"},
        }

        mock_read = MagicMock(return_value=json.dumps(mock_response).encode())
        mock_resp = MagicMock()
        mock_resp.read = mock_read
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "fake-token"}):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ex = DiscordExtractor()
                profile = ex.extract(
                    {"id": "discord", "name": "Discord"},
                    "270904126974590976",
                )

        assert profile.site_id == "discord"
        assert profile.site_name == "Discord"
        assert profile.username == "270904126974590976"
        assert profile.url == "https://discord.com/users/270904126974590976"
        assert profile.display_name == "Test User"
        assert profile.bio == "Hello, I am a test user!"
        assert profile.avatar_url == (
            "https://cdn.discordapp.com/avatars/270904126974590976/abc123def456.png?size=512"
        )
        assert profile.extra is not None
        assert profile.extra["banner_url"] == (
            "https://cdn.discordapp.com/banners/270904126974590976/banner_hash_001.png?size=512"
        )
        assert profile.extra["accent_color"] == 5793266
        assert profile.extra["public_flags"] == 4194304
        assert profile.extra["avatar_decoration"] == {"asset": "a_123", "sku_id": "sku_1"}
        assert profile.empty is False

    def test_extract_animated_avatar(self) -> None:
        """Animated avatars (a_ prefix) should produce .gif URLs."""
        mock_response = {
            "id": "123456",
            "username": "gifuser",
            "discriminator": "0001",
            "global_name": None,
            "avatar": "a_gifhash123",
        }

        mock_read = MagicMock(return_value=json.dumps(mock_response).encode())
        mock_resp = MagicMock()
        mock_resp.read = mock_read
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "fake-token"}):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ex = DiscordExtractor()
                profile = ex.extract(
                    {"id": "discord", "name": "Discord"},
                    "123456",
                )

        assert profile.display_name == "gifuser"  # fallback to username
        assert profile.avatar_url == (
            "https://cdn.discordapp.com/avatars/123456/a_gifhash123.gif?size=512"
        )

    def test_extract_minimal_response(self) -> None:
        """API returning only minimal fields should not crash."""
        mock_response = {
            "id": "999999",
            "username": "minimal",
        }

        mock_read = MagicMock(return_value=json.dumps(mock_response).encode())
        mock_resp = MagicMock()
        mock_resp.read = mock_read
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "fake-token"}):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ex = DiscordExtractor()
                profile = ex.extract(
                    {"id": "discord", "name": "Discord"},
                    "999999",
                )

        assert profile.site_id == "discord"
        assert profile.display_name == "minimal"
        assert profile.bio is None
        assert profile.avatar_url is None
        assert profile.extra is None or profile.extra == {}
        # Not "empty" because display_name is set
        assert profile.empty is False

    def test_extract_network_failure_returns_empty_profile(self) -> None:
        """Network errors should be caught, returning empty profile."""
        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "fake-token"}):
            with patch(
                "urllib.request.urlopen",
                side_effect=OSError("Network error"),
            ):
                ex = DiscordExtractor()
                profile = ex.extract(
                    {"id": "discord", "name": "Discord"},
                    "123456",
                )

        assert profile.site_id == "discord"
        assert profile.empty is True

    def test_extract_json_decode_error_returns_empty_profile(self) -> None:
        """Invalid JSON response should be caught, returning empty profile."""
        mock_read = MagicMock(return_value=b"not valid json")
        mock_resp = MagicMock()
        mock_resp.read = mock_read
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "fake-token"}):
            with patch("urllib.request.urlopen", return_value=mock_resp):
                ex = DiscordExtractor()
                profile = ex.extract(
                    {"id": "discord", "name": "Discord"},
                    "123456",
                )

        assert profile.site_id == "discord"
        assert profile.empty is True
