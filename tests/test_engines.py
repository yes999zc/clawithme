"""Tests for Engine — detection logic with template sandbox."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

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

    def test_unknown_var_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown template variable"):
            Engine._substitute(
                "https://example.com/{unknown_var}", {}, "test"
            )


class TestEngineProbe:
    @patch("scrapling.Fetcher.get")
    def test_status_code_probe_existing(self, mock_get):
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://example.com"
        mock_page.text = ""
        mock_page.headers = {}
        mock_page.body = b""
        mock_get.return_value = mock_page

        engine = Engine({"name": "test", "classifier": "status_code"})
        result = engine.probe(ZHIHU_SITE, "zhangjiawei")

        assert result.exists is True
        assert result.status_code == 200
        assert result.classifier == "status_code"

    @patch("scrapling.Fetcher.get")
    def test_status_code_probe_missing(self, mock_get):
        mock_page = MagicMock()
        mock_page.status = 404
        mock_page.url = "https://example.com"
        mock_page.text = ""
        mock_page.headers = {}
        mock_page.body = b""
        mock_get.return_value = mock_page

        engine = Engine({"name": "test", "classifier": "status_code"})
        result = engine.probe(ZHIHU_SITE, "nonexistent")

        assert result.exists is False
        assert result.status_code == 404

    @patch("scrapling.Fetcher.get")
    def test_message_probe_presence(self, mock_get):
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://example.com"
        mock_page.text = "Welcome Alice! Edit your profile here."
        mock_page.headers = {}
        mock_page.body = b""
        mock_get.return_value = mock_page

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

    @patch("scrapling.Fetcher.get")
    def test_message_probe_absence(self, mock_get):
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "https://example.com"
        mock_page.text = "User not found. Please try again."
        mock_page.headers = {}
        mock_page.body = b""
        mock_get.return_value = mock_page

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

    def test_playwright_fetch_closes_resources_on_page_error(self, monkeypatch):
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_page.goto.side_effect = TimeoutError("navigation timed out")
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_sync_playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_pw

        playwright_module = ModuleType("playwright")
        sync_api_module = ModuleType("playwright.sync_api")
        sync_api_module.sync_playwright = mock_sync_playwright
        monkeypatch.setitem(sys.modules, "playwright", playwright_module)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)

        engine = Engine({"name": "test", "classifier": "status_code"})
        result = engine._fetch_playwright("https://example.com")

        assert result is None
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()

    def test_playwright_fetch_suppresses_close_errors(self, monkeypatch):
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.headers = {}
        mock_page.goto.return_value = mock_resp
        mock_page.content.return_value = "ok"
        mock_page.url = "https://example.com"
        mock_context.close.side_effect = OSError("close failed")
        mock_context.new_page.return_value = mock_page
        mock_browser.new_context.return_value = mock_context

        mock_pw = MagicMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_sync_playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_pw

        playwright_module = ModuleType("playwright")
        sync_api_module = ModuleType("playwright.sync_api")
        sync_api_module.sync_playwright = mock_sync_playwright
        monkeypatch.setitem(sys.modules, "playwright", playwright_module)
        monkeypatch.setitem(sys.modules, "playwright.sync_api", sync_api_module)

        engine = Engine({"name": "test", "classifier": "status_code"})
        result = engine._fetch_playwright("https://example.com")

        assert result is not None
        assert result.status_code == 200
        mock_context.close.assert_called_once()
        mock_browser.close.assert_called_once()
