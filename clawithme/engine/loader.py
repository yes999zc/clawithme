"""Engine loader — reads engines.json and matches sites to engines."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from clawithme.engine.engines import Engine
from clawithme.logging import get_logger

if TYPE_CHECKING:
    from clawithme.engine.http_client import HttpClient
    from clawithme.engine.proxy_manager import ProxyManager

logger = get_logger()


def load_engines(
    engines_path: str | Path | None = None,
    http_client: "HttpClient | None" = None,
    proxy_manager: "ProxyManager | None" = None,
) -> dict[str, Engine]:
    """Load all engine definitions from engines.json.

    If *http_client* is provided, all engines share it as fallback.
    If *proxy_manager* is provided, engines use per-tier proxy selection.
    Otherwise each engine creates its own default HttpClient.

    Returns: {engine_name: Engine instance}
    """
    if engines_path is None:
        engines_path = Path(__file__).resolve().parent.parent.parent / "data" / "engines.json"

    with open(engines_path) as f:
        raw = json.load(f)

    engines: dict[str, Engine] = {}
    for ref, engine_def in raw.items():
        engines[ref] = Engine(
            engine_def,
            http_client=http_client,
            proxy_manager=proxy_manager,
        )

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
