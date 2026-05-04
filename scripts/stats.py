#!/usr/bin/env python3
"""Statistics for clawithme site database."""

import json
from pathlib import Path
from collections import Counter

SITES_DIR = Path(__file__).resolve().parent.parent / "data" / "sites"


def main():
    sites = []
    for json_file in SITES_DIR.rglob("*.json"):
        if "migrated" in str(json_file):
            continue  # skip migration output
        site = json.loads(json_file.read_text())
        sites.append(site)

    active = [s for s in sites if not s.get("deprecated")]
    deprecated = [s for s in sites if s.get("deprecated")]

    print(f"Total sites: {len(sites)}")
    print(f"  Active:    {len(active)}")
    print(f"  Deprecated: {len(deprecated)}")
    print()

    # By primary category
    by_primary = Counter(s["classification"]["primary"] for s in active)
    print("By category:")
    for cat, count in by_primary.most_common():
        print(f"  {cat:12s} {count}")

    # By identity_type
    by_idtype = Counter(s["classification"]["identity_type"] for s in active)
    print("\nBy identity type:")
    for t, count in by_idtype.most_common():
        print(f"  {t:15s} {count}")

    # By geo_region
    by_geo = Counter(s["classification"]["geo_region"] for s in active)
    print("\nBy region:")
    for r, count in by_geo.most_common():
        print(f"  {r:10s} {count}")

    # By engine
    by_engine = Counter(s.get("engine_ref", "?") for s in active)
    print("\nBy engine:")
    for e, count in by_engine.most_common():
        print(f"  {e:22s} {count}")

    # Top user_scale
    by_scale = sorted(active, key=lambda s: s["classification"].get("user_scale", 0), reverse=True)
    print("\nTop 10 by user scale:")
    for s in by_scale[:10]:
        print(f"  {s['name']:20s} {s['classification'].get('user_scale', 0):>12,}")


if __name__ == "__main__":
    main()
