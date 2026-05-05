"""Tests for signals/correlation.py — multi-signal clustering."""

from clawithme.crawler.base import Profile
from clawithme.signals.correlation import Cluster, CorrelationEngine


def _profile(site_id: str, **kw) -> Profile:
    defaults = dict(site_name=site_id, url=f"https://{site_id}.com/user", username=site_id)
    defaults.update(kw)
    return Profile(site_id=site_id, **defaults)


class TestCorrelationEngine:
    def test_single_profile(self):
        engine = CorrelationEngine()
        p = _profile("github")
        clusters = engine.correlate([p])
        assert len(clusters) == 1
        assert clusters[0].profiles == [p]
        assert clusters[0].confidence == 1.0

    def test_no_match_separate_clusters(self):
        engine = CorrelationEngine()
        a = _profile("github", avatar_phash="c60c9933d19bcccd")
        b = _profile("zhihu", avatar_phash="8c857bd4b24bc999")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 2

    def test_avatar_phash_match_same_cluster(self):
        engine = CorrelationEngine()
        phash = "a3f8c2d1e4b5a3f8"
        a = _profile("github", avatar_phash=phash)
        b = _profile("zhihu", avatar_phash=phash)
        clusters = engine.correlate([a, b])
        assert len(clusters) == 1
        assert len(clusters[0].profiles) == 2
        assert clusters[0].confidence > 0
        assert "avatar_phash" in clusters[0].signals

    def test_transitive_closure(self):
        """A↔B by phash, B↔C by email → A,B,C same cluster."""
        engine = CorrelationEngine()
        phash = "a3f8c2d1e4b5a3f8"
        a = _profile("github", avatar_phash=phash)
        b = _profile("zhihu", avatar_phash=phash, email="alice@example.com")
        c = _profile("gitlab", email="alice@example.com")
        clusters = engine.correlate([a, b, c])
        assert len(clusters) == 1
        assert len(clusters[0].profiles) == 3

    def test_email_match(self):
        engine = CorrelationEngine()
        a = _profile("github", email="alice@example.com")
        b = _profile("gitlab", email="alice@example.com")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 1
        assert clusters[0].confidence == 1.0
        assert "email" in clusters[0].signals

    def test_phone_match(self):
        engine = CorrelationEngine()
        a = _profile("github", phone="+86 138-0000-1234")
        b = _profile("zhihu", phone="13800001234")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 1
        assert clusters[0].confidence == 0.95
        assert "phone" in clusters[0].signals

    def test_mixed_signals(self):
        """A-B by phash, C-D by email, no cross-match → 2 clusters."""
        engine = CorrelationEngine()
        phash = "a3f8c2d1e4b5a3f8"
        a = _profile("github", avatar_phash=phash)
        b = _profile("zhihu", avatar_phash=phash)
        c = _profile("gitlab", email="bob@example.com")
        d = _profile("stackoverflow", email="bob@example.com")
        clusters = engine.correlate([a, b, c, d])
        assert len(clusters) == 2

    def test_detected_signals_only_actual_matches(self):
        """Profiles with different avatars matched by email → signals = [email] only."""
        engine = CorrelationEngine()
        a = _profile("github", avatar_phash="c60c9933d19bcccd", email="alice@ex.com")
        b = _profile("zhihu", avatar_phash="8c857bd4b24bc999", email="alice@ex.com")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 1
        assert clusters[0].signals == ["email"]

    def test_username_similarity_match(self):
        """alice on GitHub vs alice_cn on Zhihu → same cluster via username."""
        engine = CorrelationEngine()
        a = _profile("github", username="alice")
        b = _profile("zhihu", username="alice_cn")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 1
        assert "username" in clusters[0].signals

    def test_anti_merge_username_contradiction(self):
        """Same username, very different display_name + location → NOT merged."""
        engine = CorrelationEngine()
        a = _profile("github", username="john",
                     display_name="John Smith", location="New York")
        b = _profile("zhihu", username="john",
                     display_name="张伟", location="Beijing")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 2

    def test_anti_merge_same_location_still_merges(self):
        """Username match + same location → still merges despite different display_name."""
        engine = CorrelationEngine()
        a = _profile("github", username="john",
                     display_name="John Smith", location="New York")
        b = _profile("zhihu", username="john",
                     display_name="张伟", location="New York")
        clusters = engine.correlate([a, b])
        assert len(clusters) == 1
