"""Phase 4.1 — Avatar perceptual hashing for cross-platform identity matching.

Computes pHash (perceptual hash) from downloaded avatar images.
pHash allows comparing visually similar images via Hamming distance
— unlike SHA-256, which is useless for resized/re-encoded images.
"""

from __future__ import annotations

import io
from typing import NamedTuple

import imagehash
from PIL import Image

from clawithme.logging import get_logger

logger = get_logger()


class AvatarMatch(NamedTuple):
    """Result of comparing two avatar pHashes."""
    distance: int
    is_match: bool


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


def hamming_distance(phash1: str, phash2: str) -> int:
    """Count differing bits between two equal-length pHash hex strings.

    Raises ValueError if the hashes have different lengths.
    """
    if len(phash1) != len(phash2):
        raise ValueError(
            f"Cannot compare pHashes of different lengths: "
            f"{len(phash1)} vs {len(phash2)}"
        )
    return (int(phash1, 16) ^ int(phash2, 16)).bit_count()


def compare_avatars(
    phash1: str | None,
    phash2: str | None,
    threshold: int = 10,
) -> AvatarMatch:
    """Compare two avatar pHashes via Hamming distance.

    Returns AvatarMatch(distance, is_match).
    is_match is True when distance <= threshold.
    Returns distance=-1, is_match=False if either pHash is None.
    """
    if phash1 is None or phash2 is None:
        return AvatarMatch(distance=-1, is_match=False)
    dist = hamming_distance(phash1, phash2)
    return AvatarMatch(distance=dist, is_match=dist <= threshold)
