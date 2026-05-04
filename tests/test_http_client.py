"""Tests for HttpClient — Scrapling-backed HTTP client."""

from unittest.mock import MagicMock, patch

import pytest

from clawithme.engine.http_client import HttpClient, HttpResponse


class TestHttpResponse:
    def test_ok_status(self):
        resp = HttpResponse(status_code=200, url="http://example.com", text="ok")
        assert resp.ok is True
        assert resp.is_redirect is False
        assert resp.is_not_found is False

    def test_not_found(self):
        resp = HttpResponse(status_code=404, url="http://example.com", text="not found")
        assert resp.ok is False
        assert resp.is_not_found is True

    def test_redirect(self):
        resp = HttpResponse(status_code=302, url="http://example.com", text="redirect")
        assert resp.is_redirect is True


class TestHttpClient:
    @patch("clawithme.engine.http_client.Fetcher")
    def test_get_returns_response(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.url = "http://example.com"
        mock_page.text = "hello"
        mock_page.headers = {"Content-Type": "text/html"}
        mock_page.body = b"hello"
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        client = HttpClient()
        resp = client.get("http://example.com")

        assert resp.status_code == 200
        assert resp.text == "hello"
        assert resp.ok is True

    @patch("clawithme.engine.http_client.Fetcher")
    def test_get_404(self, mock_fetcher_class):
        mock_fetcher = MagicMock()
        mock_page = MagicMock()
        mock_page.status = 404
        mock_page.url = "http://example.com/404"
        mock_page.text = ""
        mock_page.headers = {}
        mock_page.body = b""
        mock_fetcher.get.return_value = mock_page
        mock_fetcher_class.return_value = mock_fetcher

        client = HttpClient()
        resp = client.get("http://example.com/404")

        assert resp.status_code == 404
        assert resp.ok is False
        assert resp.is_not_found is True
