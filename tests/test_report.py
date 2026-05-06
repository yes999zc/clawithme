"""Tests for report/generator.py — HTML report generation."""

import json

import pytest

from clawithme.crawler.base import Profile
from clawithme.report.generator import export_json, generate_report
from clawithme.signals.correlation import CorrelationEngine


def _sample_hits():
    return [
        {"site_name": "GitHub", "url": "https://github.com/alice", "status": 200},
        {"site_name": "GitLab", "url": "https://gitlab.com/alice", "status": 200},
    ]


def _sample_profiles():
    return [
        {
            "site_id": "github",
            "display_name": "Alice",
            "bio": "Full-stack developer. Open source enthusiast.",
            "location": "Shanghai",
            "avatar_url": None,
            "followers": 42,
        },
        {
            "site_id": "zhihu",
            "display_name": "Alice CN",
            "bio": "",
            "location": "",
            "avatar_url": None,
            "followers": None,
        },
    ]


def _sample_clusters():
    engine = CorrelationEngine()
    p1 = Profile("github", "GitHub", "https://github.com/alice", "alice",
                 avatar_phash="a3f8c2d1e4b5a3f8", email="alice@ex.com")
    p2 = Profile("zhihu", "知乎", "https://zhihu.com/people/alice", "alice_cn",
                 avatar_phash="a3f8c2d1e4b5a3f8")
    return engine.correlate([p1, p2])


class TestGenerateReport:
    def test_returns_html_string(self):
        html = generate_report([], [], [], "alice")
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "<title>CLAWITHME 身份报告：alice</title>" in html

    def test_includes_sites(self):
        html = generate_report(_sample_hits(), [], [], "alice")
        assert "GitHub" in html
        assert "github.com/alice" in html
        assert "200" in html

    def test_includes_profiles(self):
        html = generate_report([], _sample_profiles(), [], "alice")
        assert "Alice" in html
        assert "Full-stack developer" in html
        assert "Shanghai" in html

    def test_includes_clusters(self):
        html = generate_report([], [], _sample_clusters(), "alice")
        assert "Cluster 1" in html
        assert "avatar_phash" in html

    def test_empty_report(self):
        html = generate_report([], [], [], "alice")
        assert "未发现站点" in html
        assert "未提取到资料" in html
        assert "未发现身份关联" in html

    def test_html_escapes_special_chars(self):
        profiles = [{
            "site_id": "test",
            "display_name": "<script>alert(1)</script>",
            "bio": "a & b",
            "location": "",
            "avatar_url": None,
            "followers": None,
        }]
        html = generate_report([], profiles, [], "alice")
        assert "<script>" not in html
        assert "&lt;script&gt;" in html
        assert "&amp;" in html


class TestExportJson:
    def test_returns_valid_json(self):
        clusters = _sample_clusters()
        result = export_json(_sample_hits(), _sample_profiles(), clusters, "alice")
        data = json.loads(result)
        assert data["tool"] == "clawithme"
        assert data["username"] == "alice"

    def test_includes_clusters(self):
        clusters = _sample_clusters()
        result = export_json([], [], clusters, "alice")
        data = json.loads(result)
        assert len(data["clusters"]) == 1
        assert data["clusters"][0]["confidence"] == 0.8
        assert "avatar_phash" in data["clusters"][0]["signals"]


# ── PDF export ─────────────────────────────────────────────────


def _sample_hits_full():
    return [
        {"site_name": "GitHub", "url": "https://github.com/alice", "status": 200,
         "site_def": {"id": "github", "classification": {"primary": "devtools"}}},
    ]


def _sample_profiles_full():
    return [
        {
            "site_id": "github",
            "display_name": "Alice",
            "bio": "Full-stack developer.",
            "location": "Shanghai",
            "avatar_url": None,
            "follower_count": 42,
        },
    ]


class TestExportPdf:
    @classmethod
    def setup_class(cls):
        """Skip all PDF tests if WeasyPrint system deps are unavailable."""
        try:
            from weasyprint import HTML  # noqa: F401
        except (OSError, ImportError):
            pytest.skip("WeasyPrint system dependencies (Pango, GObject) not available")

    def test_returns_bytes(self):
        """export_pdf returns raw PDF bytes."""
        from clawithme.report.generator import export_pdf
        pdf = export_pdf([], [], [], "alice")
        assert isinstance(pdf, bytes)
        assert len(pdf) > 0

    def test_has_pdf_signature(self):
        """PDF bytes start with %PDF- signature."""
        from clawithme.report.generator import export_pdf
        pdf = export_pdf([], [], [], "alice")
        assert pdf.startswith(b"%PDF-")

    def test_with_hits_and_profiles(self):
        """Real data produces valid PDF."""
        from clawithme.report.generator import export_pdf
        pdf = export_pdf(
            _sample_hits_full(), _sample_profiles_full(),
            _sample_clusters(), "alice",
        )
        assert len(pdf) > 1000  # non-trivial size
        assert pdf.startswith(b"%PDF-")

    def test_html_escaped_in_pdf(self):
        """XSS payload does not reach PDF as raw HTML."""
        from clawithme.report.generator import export_pdf
        profiles = [{
            "site_id": "test",
            "display_name": "<script>alert(1)</script>",
            "bio": "a & b",
            "location": "",
            "avatar_url": None,
            "follower_count": None,
        }]
        pdf = export_pdf([], profiles, [], "alice")
        text = pdf.decode("latin-1", errors="ignore")
        assert "<script>" not in text
        assert "&lt;script&gt;" in text

    def test_empty_data_still_valid_pdf(self):
        """Empty hits/profiles/clusters still produce valid PDF."""
        from clawithme.report.generator import export_pdf
        pdf = export_pdf([], [], [], "alice")
        assert pdf.startswith(b"%PDF-")
        assert len(pdf) > 500  # header + boilerplate
