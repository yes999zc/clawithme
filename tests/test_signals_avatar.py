"""Tests for signals/avatar.py — perceptual hash computation."""

import io

from PIL import Image, ImageDraw

from clawithme.signals.avatar import compute_phash


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
