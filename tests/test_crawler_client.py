"""Tests for CrawlerClient — delegates to engine's HttpClient."""

from unittest.mock import MagicMock, patch
from clawithme.crawler.client import CrawlerClient, _check_dynamic


class TestCheckDynamic:
    @patch("clawithme.crawler.client._DYNAMIC_AVAILABLE", None)
    def test_returns_bool(self):
        result = _check_dynamic()
        assert isinstance(result, bool)


class TestCrawlerClient:
    def test_http_property_creates_once(self):
        with patch("clawithme.crawler.client.HttpClient") as mock_cls:
            client = CrawlerClient()
            h1 = client.http
            h2 = client.http
            assert h1 is h2
            mock_cls.assert_called_once()

    def test_fetch_static_returns_response(self):
        with patch("clawithme.crawler.client.HttpClient") as mock_http_cls:
            mock_http = MagicMock()
            mock_fetcher = MagicMock()
            mock_page = MagicMock()
            mock_page.status = 200
            mock_page.url = "http://example.com"
            mock_page.text = "hello"
            mock_fetcher.get.return_value = mock_page
            mock_http.static = mock_fetcher
            mock_http_cls.return_value = mock_http

            client = CrawlerClient()
            resp = client.fetch_static("http://example.com")
            assert resp.status == 200
            assert resp.text == "hello"

    def test_dynamic_available_or_graceful(self):
        client = CrawlerClient()
        resp = client.fetch_dynamic("http://example.com")
        if resp is None:
            return  # Graceful degradation
        assert resp.status == 200
        assert resp.html_content or resp.body
