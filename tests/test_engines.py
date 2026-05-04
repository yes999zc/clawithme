"""Tests for Engine — detection logic with template sandbox."""

import pytest
from unittest.mock import MagicMock, patch
from clawithme.engine.engines import Engine, EngineResult


ZHIHU_SITE = {
    "id": "zhihu",
    "name": "知乎",
    "check": {
        "probe_url": "https://www.zhihu.com/api/v4/members/{username}",
        "expected": 200,
        "known_accounts": ["zhangjiawei"],
    },
}


class TestEngineTemplateSubstitution:
    def test_username_substitution(self):
        result = Engine._substitute(
            "https://example.com/{username}", {}, "alice"
        )
        assert result == "https://example.com/alice"

    def test_e_code_substitution(self):
        check = {"expected": 200}
        result = Engine._substitute("{e_code}", check, "test")
        assert result == "200"

    def test_multiple_vars(self):
        result = Engine._substitute(
            "https://{username}.example.com/status/{e_code}",
            {"expected": 404},
            "bob",
        )
        assert result == "https://bob.example.com/status/404"

    def test_unknown_var_unchanged(self):
        result = Engine._substitute(
            "https://example.com/{unknown_var}", {}, "test"
        )
        assert result == "https://example.com/{unknown_var}"


class TestEngineProbe:
    @patch("clawithme.engine.http_client.Fetcher")
    def test_status_code_probe_existing(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://example.com"
        mock_page.text = ""
        mock_page.headers = {}
        mock_page.body = b""
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        engine = Engine({"name": "test", "classifier": "status_code"})
        result = engine.probe(ZHIHU_SITE, "zhangjiawei")

        assert result.exists is True
        assert result.status_code == 200
        assert result.classifier == "status_code"

    @patch("clawithme.engine.http_client.Fetcher")
    def test_status_code_probe_missing(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 404
        mock_page.url = "https://example.com"
        mock_page.text = ""
        mock_page.headers = {}
        mock_page.body = b""
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        engine = Engine({"name": "test", "classifier": "status_code"})
        result = engine.probe(ZHIHU_SITE, "nonexistent")

        assert result.exists is False
        assert result.status_code == 404

    @patch("clawithme.engine.http_client.Fetcher")
    def test_message_probe_presence(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://example.com"
        mock_page.text = "Welcome Alice! Edit your profile here."
        mock_page.headers = {}
        mock_page.body = b""
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        engine = Engine({"name": "test", "classifier": "message"})
        site = {
            "id": "test",
            "name": "Test",
            "check": {
                "probe_url": "https://example.com/{username}",
                "presence_strs": ["Edit your profile"],
                "absence_strs": ["not found"],
            },
        }
        result = engine.probe(site, "alice")
        assert result.exists is True

    @patch("clawithme.engine.http_client.Fetcher")
    def test_message_probe_absence(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://example.com"
        mock_page.text = "User not found. Please try again."
        mock_page.headers = {}
        mock_page.body = b""
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        engine = Engine({"name": "test", "classifier": "message"})
        site = {
            "id": "test",
            "name": "Test",
            "check": {
                "probe_url": "https://example.com/{username}",
                "presence_strs": ["Edit your profile"],
                "absence_strs": ["not found"],
            },
        }
        result = engine.probe(site, "alice")
        assert result.exists is False
