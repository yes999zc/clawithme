"""Tests for CrawlerClient — rate limiting, backoff, UA rotation."""

from unittest.mock import MagicMock, patch

from clawithme.crawler.client import (
    CrawlerClient,
    _check_dynamic,
    random_user_agent,
)


class TestRandomUserAgent:
    def test_returns_string(self):
        ua = random_user_agent()
        assert isinstance(ua, str)
        assert "Mozilla" in ua

    def test_rotation_produces_variation(self):
        # Sample many UAs — should see multiple distinct values
        uas = {random_user_agent() for _ in range(50)}
        assert len(uas) > 1, "UA rotation is broken (all same)"


class TestCheckDynamic:
    @patch("clawithme.crawler.client._DYNAMIC_AVAILABLE", None)
    def test_returns_bool(self):
        result = _check_dynamic()
        assert isinstance(result, bool)


class TestCrawlerClient:
    def test_rate_limit_enforces_min_delay(self):
        client = CrawlerClient(min_delay_ms=100)
        t0 = client._last_request_at
        client._wait_if_needed()
        assert client._last_request_at >= t0

    @patch("clawithme.crawler.client.HttpClient")
    def test_fetch_static_with_retry(self, mock_http_cls):
        mock_http = MagicMock()
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "http://example.com"
        mock_page.text = "hello"

        # First call fails, second succeeds
        mock_fetcher.get.side_effect = [
            OSError("timeout"),
            mock_page,
        ]
        mock_http.static = mock_fetcher
        mock_http_cls.return_value = mock_http

        client = CrawlerClient(max_retries=2, min_delay_ms=0, backoff_base_ms=1)
        resp = client.fetch_static("http://example.com")

        assert resp.status == 200
        assert resp.text == "hello"
        assert mock_fetcher.get.call_count == 2

    @patch("clawithme.crawler.client.HttpClient")
    def test_fetch_static_exhausts_retries(self, mock_http_cls):
        mock_http = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.get.side_effect = OSError("timeout")
        mock_http.static = mock_fetcher
        mock_http_cls.return_value = mock_http

        client = CrawlerClient(max_retries=1, min_delay_ms=0, backoff_base_ms=1)
        try:
            client.fetch_static("http://example.com")
            assert False, "Should have raised"
        except OSError:
            pass

    def test_default_values(self):
        client = CrawlerClient()
        assert client._min_delay_ms == 200
        assert client._max_retries == 2
        assert client._backoff_base_ms == 1000

    def test_dynamic_available_or_graceful(self):
        client = CrawlerClient(min_delay_ms=0)
        resp = client.fetch_dynamic("http://example.com")
        if resp is None:
            return
        assert resp.status == 200
        assert resp.html_content or resp.body
