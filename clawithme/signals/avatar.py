"""Phase 4.1 — Avatar perceptual hashing for cross-platform identity matching.

Computes pHash (perceptual hash) from downloaded avatar images.
pHash allows comparing visually similar images via Hamming distance
— unlike SHA-256, which is useless for resized/re-encoded images.
"""

from __future__ import annotations

import io

import imagehash
from PIL import Image

from clawithme.logging import get_logger

logger = get_logger()


def compute_phash(image_bytes: bytes) -> str | None:
    """Compute perceptual hash from raw image bytes.

    Returns hex string (e.g. "a3f8c2d1e4b5...") or None if
    the image cannot be decoded.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        phash = imagehash.phash(img)
        return str(phash)
    except (OSError, ValueError) as e:
        logger.warning("phash_compute_failed", error=str(e))
        return None
