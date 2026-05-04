"""Tests for signals/avatar.py — perceptual hash computation and comparison."""

import io

from PIL import Image, ImageDraw

from clawithme.signals.avatar import compare_avatars, compute_phash, hamming_distance


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


# ── compare_avatars ───────────────────────────────────────────

class TestCompareAvatars:
    def test_match_same_hash(self):
        r = compare_avatars("a3f8c2d1e4b5a3f8", "a3f8c2d1e4b5a3f8")
        assert r == {"distance": 0, "is_match": True}

    def test_no_match_different_people(self):
        r = compare_avatars("c60c9933d19bcccd", "8c857bd4b24bc999")
        assert r["distance"] > 10
        assert r["is_match"] is False

    def test_either_none_returns_no_match(self):
        assert compare_avatars(None, "c60c9933d19bcccd") == {"distance": -1, "is_match": False}
        assert compare_avatars("c60c9933d19bcccd", None) == {"distance": -1, "is_match": False}
        assert compare_avatars(None, None) == {"distance": -1, "is_match": False}
