#!/usr/bin/env python3
"""Extractor health monitoring — smoke test every registered extractor.

Runs each extractor against its first known_account and reports status.
Exit codes: 0 = all OK, 1 = any degraded, 2 = any failed.

Usage:
    python scripts/extractor_health.py
    python scripts/extractor_health.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from clawithme.cli import load_all_sites
from clawithme.crawler.registry import discover_extractors
from clawithme.logging import setup_logging


NON_EMPTY_FIELDS = [
    "display_name",
    "bio",
    "avatar_url",
    "avatar_phash",
    "email",
    "phone",
    "location",
    "joined_date",
    "post_count",
    "follower_count",
    "following_count",
]


def _get_non_empty_fields(profile) -> list[str]:
    """Return field names that have non-None/non-empty values."""
    fields = []
    for fname in NON_EMPTY_FIELDS:
        val = getattr(profile, fname, None)
        if val is not None:
            fields.append(fname)
    if profile.extra:
        fields.append("extra")
    return fields


def check_extractor(site: dict, extractor_cls, username: str) -> tuple[str, list[str]]:
    """Run a single extractor and return (status, fields_found)."""
    try:
        extractor = extractor_cls()
        profile = extractor.extract(site, username)
        fields = _get_non_empty_fields(profile)

        if profile.empty:
            return "DEGRADED", fields
        if not profile.display_name:
            return "DEGRADED", fields
        return "OK", fields
    except Exception:
        return "FAILED", []


def main():
    parser = argparse.ArgumentParser(
        description="Smoke test all registered extractors"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output JSON report instead of human-readable table",
    )
    args = parser.parse_args()

    setup_logging()

    sites = load_all_sites(include_migrated=False)
    extractors = discover_extractors()

    results: list[dict] = []
    for site in sites:
        site_id = site["id"]
        known = site.get("check", {}).get("known_accounts", [])
        if not known:
            continue
        extractor_cls = extractors.get(site_id)
        if extractor_cls is None:
            continue

        username = known[0]
        status, fields = check_extractor(site, extractor_cls, username)

        results.append({
            "site_id": site_id,
            "site_name": site["name"],
            "status": status,
            "fields": fields,
        })

    results.sort(key=lambda r: ({"FAILED": 0, "DEGRADED": 1, "OK": 2}[r["status"]], r["site_id"]))

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        ok_count = sum(1 for r in results if r["status"] == "OK")
        degraded = [r for r in results if r["status"] == "DEGRADED"]
        failed = [r for r in results if r["status"] == "FAILED"]

        print("Extractor Health Report")
        print("=" * 60)
        print()
        for r in results:
            fields_str = ", ".join(r["fields"]) if r["fields"] else "(none)"
            print(f"  {r['status']:10s}  {r['site_name']:16s} ({r['site_id']:12s})  fields=[{fields_str}]")

        print()
        total = len(results)
        print(f"Summary: {ok_count} OK, {len(degraded)} degraded, {len(failed)} failed / {total} total")
        print()

    if any(r["status"] == "FAILED" for r in results):
        sys.exit(2)
    if any(r["status"] == "DEGRADED" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
