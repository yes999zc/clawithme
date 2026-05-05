"""Tests for signals/avatar.py — perceptual hash computation and comparison."""

import io

from PIL import Image, ImageDraw

from clawithme.signals.avatar import AvatarMatch, compare_avatars, compute_phash, hamming_distance, is_default_avatar


def _make_red_block() -> bytes:
    """White background with red rectangle in top-left quarter."""
    img = Image.new("RGB", (64, 64), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 31, 31], fill=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_blue_block() -> bytes:
    """White background with blue rectangle in bottom-right quarter."""
    img = Image.new("RGB", (64, 64), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([32, 32, 63, 63], fill=(0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ── compute_phash ─────────────────────────────────────────────

class TestComputePHash:
    def test_same_image_same_hash(self):
        img = _make_red_block()
        h1 = compute_phash(img)
        h2 = compute_phash(img)
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) > 0

    def test_different_images_different_hash(self):
        h1 = compute_phash(_make_red_block())
        h2 = compute_phash(_make_blue_block())
        assert h1 != h2

    def test_invalid_bytes_returns_none(self):
        assert compute_phash(b"not an image") is None


# ── hamming_distance ──────────────────────────────────────────

class TestHammingDistance:
    def test_identical_hashes(self):
        phash = "c60c9933d19bcccd"
        assert hamming_distance(phash, phash) == 0

    def test_different_people(self):
        linus = "c60c9933d19bcccd"
        karpathy = "8c857bd4b24bc999"
        dist = hamming_distance(linus, karpathy)
        assert dist > 10


# ── is_default_avatar / default avatar short-circuit ────────────

class TestDefaultAvatar:
    def test_known_default_phash_detected(self):
        # Gravatar mystery person synthetic pHash from data/default_avatars.json
        assert is_default_avatar("9a6661796786669a") is True

    def test_github_identicon_detected(self):
        assert is_default_avatar("f9a8f9b8f90606a8") is True

    def test_near_default_within_threshold(self):
        # Slightly perturbed — Hamming distance ~1, still within threshold 3
        assert is_default_avatar("9a6661796786669b") is True

    def test_non_default_not_detected(self):
        assert is_default_avatar("c60c9933d19bcccd") is False

    def test_compare_default_and_valid_returns_no_match(self):
        r = compare_avatars("9a6661796786669a", "c60c9933d19bcccd")
        assert r.is_match is False
        assert r.distance == -1

    def test_compare_valid_and_default_returns_no_match(self):
        r = compare_avatars("c60c9933d19bcccd", "f9a8f9b8f90606a8")
        assert r.is_match is False
        assert r.distance == -1

    def test_compare_two_defaults_returns_no_match(self):
        r = compare_avatars("9a6661796786669a", "f9a8f9b8f90606a8")
        assert r.is_match is False
        assert r.distance == -1

    def test_non_default_phashes_still_match_normally(self):
        r = compare_avatars("c60c9933d19bcccd", "c60c9933d19bcccd")
        assert r.is_match is True
        assert r.distance == 0

class TestCompareAvatars:
    def test_match_same_hash(self):
        r = compare_avatars("a3f8c2d1e4b5a3f8", "a3f8c2d1e4b5a3f8")
        assert r.distance == 0
        assert r.is_match is True

    def test_no_match_different_people(self):
        r = compare_avatars("c60c9933d19bcccd", "8c857bd4b24bc999")
        assert r.distance > 10
        assert r.is_match is False

    def test_either_none_returns_no_match(self):
        assert compare_avatars(None, "c60c9933d19bcccd") == AvatarMatch(distance=-1, is_match=False)
        assert compare_avatars("c60c9933d19bcccd", None) == AvatarMatch(distance=-1, is_match=False)
        assert compare_avatars(None, None) == AvatarMatch(distance=-1, is_match=False)
