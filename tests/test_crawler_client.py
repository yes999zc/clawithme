"""Tests for CrawlerClient — static fetcher wrapper."""

from unittest.mock import MagicMock, patch
from clawithme.crawler.client import CrawlerClient, _check_dynamic


class TestCheckDynamic:
    @patch("clawithme.crawler.client._DYNAMIC_AVAILABLE", None)
    def test_returns_bool(self):
        # DynamicFetcher may or may not be available; just check type
        result = _check_dynamic()
        assert isinstance(result, bool)


class TestCrawlerClient:
    @patch("clawithme.crawler.client.Fetcher")
    def test_static_property_creates_fetcher_once(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_fetcher_class.return_value = mock_fetcher

        client = CrawlerClient()
        f1 = client.static
        f2 = client.static

        assert f1 is f2
        mock_fetcher_class.assert_called_once()

    @patch("clawithme.crawler.client.Fetcher")
    def test_fetch_static_returns_response(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "http://example.com"
        mock_page.text = "hello"
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        client = CrawlerClient()
        resp = client.fetch_static("http://example.com")

        assert resp.status == 200
        assert resp.text == "hello"

    def test_dynamic_available_or_graceful(self):
        client = CrawlerClient()
        resp = client.fetch_dynamic("http://example.com")
        # Either Playwright is available → Response, or not → None
        if resp is None:
            return  # Graceful degradation
        assert resp.status == 200
        # DynamicFetcher uses .html_content, not .text
        assert resp.html_content or resp.body
