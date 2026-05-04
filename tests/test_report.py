"""Tests for report/generator.py — HTML report generation."""

from clawithme.crawler.base import Profile
from clawithme.report.generator import generate_report
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
        assert "<title>clawithme: alice</title>" in html

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
        assert "No sites found" in html
        assert "No profiles extracted" in html
        assert "No identity clusters" in html

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
