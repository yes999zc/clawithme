"""Smoke tests for CLI entry point and Phase 4 correlation pipeline."""

import pytest

from clawithme.cli import load_all_sites
from clawithme.crawler.base import Profile
from clawithme.signals.correlation import CorrelationEngine


class TestLoadAllSites:
    def test_returns_non_empty_list(self):
        sites = load_all_sites()
        assert len(sites) > 0, "No sites loaded"

    def test_all_sites_have_id(self):
        sites = load_all_sites()
        for site in sites:
            assert "id" in site, f"Site missing 'id': {site}"

    def test_no_deprecated_sites(self):
        sites = load_all_sites()
        for site in sites:
            assert not site.get("deprecated", False), (
                f"Site {site['id']} is deprecated but was loaded"
            )


class TestCorrelationPipeline:
    """Simulates CLI Phase 2+3+4: profiles + leaks → correlation."""

    def test_profiles_and_leaks_cluster_together(self):
        profile_objects = [
            Profile("github", "GitHub", "https://github.com/alice", "alice",
                    avatar_phash="a3f8c2d1e4b5a3f8", email="alice@ex.com"),
            Profile("zhihu", "知乎", "https://zhihu.com/people/alice", "alice_cn",
                    avatar_phash="a3f8c2d1e4b5a3f8"),
            # Leak sources as Profiles
            Profile("leak:adobe", "Adobe Breach", "", "alice_dev",
                    email="alice@ex.com", phone="13800001234"),
            Profile("leak:linkedin", "LinkedIn Breach", "", "alice99",
                    phone="13800001234"),
        ]

        engine = CorrelationEngine()
        clusters = engine.correlate(profile_objects)

        # github↔zhihu(phash) + github↔adobe(email) + adobe↔linkedin(phone)
        assert len(clusters) == 1
        assert len(clusters[0].profiles) == 4
        assert clusters[0].confidence > 0.8
        assert len(clusters[0].signals) >= 2

    def test_unrelated_profiles_stay_separate(self):
        alice = Profile("github", "GitHub", "https://github.com/alice", "alice",
                        avatar_phash="a3f8c2d1e4b5a3f8")
        bob = Profile("gitlab", "GitLab", "https://gitlab.com/bob", "bob",
                      avatar_phash="ffffffffffffffff")
        engine = CorrelationEngine()
        clusters = engine.correlate([alice, bob])
        assert len(clusters) == 2
