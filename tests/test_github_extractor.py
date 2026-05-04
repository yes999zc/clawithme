"""Tests for GithubExtractor."""

from unittest.mock import MagicMock, patch

from clawithme.crawler.extractors.github import GithubExtractor
from clawithme.crawler.utils import parse_count


class TestParseCount:
    def test_plain_number(self):
        assert parse_count("123") == 123

    def test_k_suffix(self):
        assert parse_count("301k") == 301000

    def test_decimal_k(self):
        assert parse_count("1.2k") == 1200

    def test_with_comma(self):
        assert parse_count("1,234") == 1234

    def test_invalid(self):
        assert parse_count("abc") is None

    def test_empty(self):
        assert parse_count("") is None


class TestGithubExtractor:
    def test_can_handle_github(self):
        ex = GithubExtractor()
        assert ex.can_handle({"id": "github"}) is True

    def test_can_handle_other(self):
        ex = GithubExtractor()
        assert ex.can_handle({"id": "twitter"}) is False

    def test_requires_dynamic_false(self):
        ex = GithubExtractor()
        assert ex.requires_dynamic is False

    @patch("clawithme.crawler.client.HttpClient")
    def test_extract_with_mock_response(self, mock_http_cls):
        mock_http = MagicMock()
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://github.com/testuser"
        mock_page.text = "mock"
        mock_page.body = b"mock"

        mock_page.css.side_effect = lambda sel: {
            "span.p-name": [MagicMock(text="Test User", attrib={})],
            "div.p-note": [MagicMock(text="A test bio", attrib={})],
            "img.avatar-user": [MagicMock(
                text="",
                attrib={"src": "https://avatars.example.com/u/1"}
            )],
            "li[itemprop=\"homeLocation\"] .p-label": [
                MagicMock(text="Shanghai", attrib={})
            ],
            "a[href*=\"followers\"] span": [
                MagicMock(text="42", attrib={})
            ],
            "a[href*=\"following\"] span": [
                MagicMock(text="10", attrib={})
            ],
        }.get(sel, [])

        mock_fetcher.get.return_value = mock_page
        mock_http.static = mock_fetcher
        mock_http_cls.return_value = mock_http

        ex = GithubExtractor()
        profile = ex.extract(
            {"id": "github", "name": "GitHub"}, "testuser"
        )

        assert profile.site_id == "github"
        assert profile.display_name == "Test User"
        assert profile.bio == "A test bio"
        assert profile.avatar_url == "https://avatars.example.com/u/1"
        assert profile.location == "Shanghai"
        assert profile.follower_count == 42
        assert profile.following_count == 10
        assert profile.empty is False

    @patch("clawithme.crawler.client.HttpClient")
    def test_extract_404_returns_empty_profile(self, mock_http_cls):
        mock_http = MagicMock()
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 404
        mock_fetcher.get.return_value = mock_page
        mock_http.static = mock_fetcher
        mock_http_cls.return_value = mock_http

        ex = GithubExtractor()
        profile = ex.extract(
            {"id": "github", "name": "GitHub"}, "nonexistent"
        )

        assert profile.site_id == "github"
        assert profile.empty is True
