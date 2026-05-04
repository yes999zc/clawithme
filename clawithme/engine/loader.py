"""Engine loader — reads engines.json and matches sites to engines."""

from __future__ import annotations

import json
from pathlib import Path

from clawithme.engine.engines import Engine
from clawithme.logging import get_logger

logger = get_logger()


def load_engines(engines_path: str | Path | None = None) -> dict[str, Engine]:
    """Load all engine definitions from engines.json.

    Returns: {engine_name: Engine instance}
    """
    if engines_path is None:
        engines_path = Path(__file__).resolve().parent.parent.parent / "data" / "engines.json"

    with open(engines_path) as f:
        raw = json.load(f)

    engines: dict[str, Engine] = {}
    for ref, engine_def in raw.items():
        engines[ref] = Engine(engine_def)

    logger.info("engines_loaded", count=len(engines), refs=list(engines.keys()))
    return engines


def get_engine_for_site(
    site: dict, engines: dict[str, Engine]
) -> Engine | None:
    """Match a site to its engine."""
    ref = site.get("engine_ref")
    if ref and ref in engines:
        return engines[ref]

    logger.warning("engine_not_found", site_id=site.get("id"), engine_ref=ref)
    return None
