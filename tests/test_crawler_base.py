"""Tests for crawler base classes."""

from clawithme.crawler.base import Profile, ProfileExtractor


class TestProfile:
    def test_empty_profile_is_empty(self):
        p = Profile(site_id="test", site_name="Test", url="http://x", username="u")
        assert p.empty is True

    def test_profile_with_display_name_not_empty(self):
        p = Profile(
            site_id="t", site_name="T", url="http://x",
            username="u", display_name="U"
        )
        assert p.empty is False

    def test_profile_with_bio_not_empty(self):
        p = Profile(
            site_id="t", site_name="T", url="http://x",
            username="u", bio="hello"
        )
        assert p.empty is False

    def test_extra_dict_defaults_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x", username="u")
        assert p.extra == {}

    def test_extra_stores_custom_data(self):
        p = Profile(site_id="t", site_name="T", url="http://x", username="u",
                     extra={"custom_key": "value"})
        assert p.extra["custom_key"] == "value"

    def test_zero_followers_not_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x",
                     username="u", follower_count=0)
        assert p.empty is False

    def test_only_following_count_not_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x",
                     username="u", following_count=5)
        assert p.empty is False

    def test_only_avatar_phash_not_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x",
                     username="u", avatar_phash="abc123")
        assert p.empty is False

    def test_only_email_not_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x",
                     username="u", email="a@b.com")
        assert p.empty is False

    def test_only_phone_not_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x",
                     username="u", phone="13800001234")
        assert p.empty is False


class FakeExtractor(ProfileExtractor):
    site_id = "fake"

    def can_handle(self, site: dict) -> bool:
        return site.get("id") == "fake"

    def extract(self, site: dict, username: str) -> Profile:
        return Profile(
            site_id="fake", site_name="Fake",
            url="http://x", username=username,
        )


class TestProfileExtractor:
    def test_can_handle_match(self):
        ex = FakeExtractor()
        assert ex.can_handle({"id": "fake"}) is True

    def test_can_handle_no_match(self):
        ex = FakeExtractor()
        assert ex.can_handle({"id": "other"}) is False

    def test_extract_returns_profile(self):
        ex = FakeExtractor()
        profile = ex.extract({"id": "fake", "name": "Fake"}, "testuser")
        assert profile.site_id == "fake"
        assert profile.username == "testuser"
