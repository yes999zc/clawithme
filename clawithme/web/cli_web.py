"""Shared helpers for web UI (avoid importing cli.py directly)."""

from __future__ import annotations

import json
from pathlib import Path


def load_all_sites(include_migrated: bool = False) -> list[dict]:
    """Load all non-deprecated site definitions."""
    sites_dir = Path(__file__).resolve().parent.parent.parent / "data" / "sites"
    sites: list[dict] = []

    for json_file in sorted(sites_dir.rglob("*.json")):
        if not include_migrated and "migrated" in json_file.parts:
            continue
        site = json.loads(json_file.read_text())
        if site.get("deprecated", False):
            continue
        sites.append(site)
    return sites
