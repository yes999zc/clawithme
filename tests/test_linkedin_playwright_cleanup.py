"""Tests for LinkedIn Playwright cleanup."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

from clawithme.crawler.extractors.linkedin import _fetch_playwright_page


def test_linkedin_playwright_fetch_closes_resources_on_page_error(monkeypatch):
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

    result = _fetch_playwright_page(
        "https://www.linkedin.com/in/example",
        [{"name": "li_at", "value": "cookie", "domain": ".linkedin.com"}],
    )

    assert result is None
    mock_context.close.assert_called_once()
    mock_browser.close.assert_called_once()
