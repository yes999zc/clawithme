#!/usr/bin/env python3
"""Migrate maigret-format site data to clawithme schema.

Usage: python scripts/migrate_maigret.py <maigret_data.json>
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SITES_DIR = DATA_DIR / "sites"
SCHEMA_PATH = DATA_DIR / "schema.json"


def map_tags_to_classification(tags: list[str]) -> dict:
    """Heuristic mapping from maigret tags to clawithme classification."""
    tag_str = " ".join(tags).lower() if tags else ""

    # Identity type
    if any(t in tag_str for t in ["social", "messaging"]):
        identity_type = "virtual_social"
    elif any(t in tag_str for t in ["coding", "tech"]):
        identity_type = "professional"
    elif any(t in tag_str for t in ["forum"]):
        identity_type = "anonymous"
    else:
        identity_type = "virtual_social"

    # Primary category
    if any(t in tag_str for t in ["social", "messaging"]):
        primary = "social"
    elif any(t in tag_str for t in ["coding", "tech"]):
        primary = "devtools"
    elif any(t in tag_str for t in ["forum"]):
        primary = "forum"
    elif any(t in tag_str for t in ["photo", "video"]):
        primary = "media"
    elif any(t in tag_str for t in ["music"]):
        primary = "music"
    elif any(t in tag_str for t in ["blog"]):
        primary = "blog"
    elif any(t in tag_str for t in ["gaming"]):
        primary = "gaming"
    else:
        primary = "social"

    return {
        "primary": primary,
        "identity_type": identity_type,
        "geo_region": "global",
        "user_scale": 0,
        "tags": tags,
    }


def migrate_site(name: str, maigret_site: dict) -> dict | None:
    """Convert a single maigret-format site to clawithme format."""
    try:
        site_id = name.lower().replace(" ", "_").replace("/", "_")

        check_type = maigret_site.get("checkType", "status_code")
        if check_type == "status_code":
            engine_ref = "base_http_status"
        elif check_type == "message":
            engine_ref = "base_http_message"
        elif check_type == "headers":
            engine_ref = "base_http_headers"
        else:
            engine_ref = "base_http_status"

        classification = map_tags_to_classification(maigret_site.get("tags", []))
        classification["user_scale"] = maigret_site.get("alexaRank", 0)

        claw_site = {
            "id": site_id,
            "name": name,
            "canonical_url": maigret_site.get("urlMain", maigret_site.get("url", "")),
            "engine_ref": engine_ref,
            "classification": classification,
            "rankings": {"alexa": maigret_site.get("alexaRank")} if maigret_site.get("alexaRank") else {},
            "check": {
                "probe_url": maigret_site.get("url", maigret_site.get("urlProbe", "")),
                "regex": maigret_site.get("regexCheck"),
                "known_accounts": [maigret_site["usernameClaimed"]] if maigret_site.get("usernameClaimed") else [],
                "known_unclaimed": [maigret_site["usernameUnclaimed"]] if maigret_site.get("usernameUnclaimed") else [],
                "headers": maigret_site.get("headers", {}),
                "error_flags": {},
            },
            "nsfw": maigret_site.get("tags", []) and "nsfw" in " ".join(maigret_site.get("tags", [])).lower(),
            "deprecated": False,
            "source": "maigret_migration",
            "last_updated": datetime.now(UTC).isoformat(),
        }

        if check_type == "message":
            claw_site["check"]["presence_strs"] = maigret_site.get("presenseStrs", [])
            claw_site["check"]["absence_strs"] = maigret_site.get("absenceStrs", [])

        return claw_site
    except Exception as e:
        print(f"  ⚠️ Skipping {maigret_site.get('name','?')}: {e}")
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/migrate_maigret.py <maigret_data.json>")
        print("  Input: maigret-format data.json (dict or list)")
        print("  Output: clawithme-format JSON files in data/sites/migrated/")
        sys.exit(1)

    schema = json.loads(SCHEMA_PATH.read_text())
    from jsonschema import validate

    raw = json.loads(Path(sys.argv[1]).read_text())

    # Handle both dict and list formats
    if isinstance(raw, dict):
        if "sites" in raw:
            sites_items = list(raw["sites"].items())
        else:
            sites_items = list(raw.items())
    else:
        sites_items = [(s.get("name", f"site_{i}"), s) for i, s in enumerate(raw)]

    print(f"Migrating {len(sites_items)} sites from maigret format...")

    migrated = 0
    skipped = 0
    out_dir = SITES_DIR / "migrated"

    for name, site in sites_items:
        if not isinstance(site, dict):
            continue
        claw_site = migrate_site(name, site)
        if claw_site is None:
            skipped += 1
            continue

        # Validate
        try:
            validate(claw_site, schema)
        except Exception as e:
            print(f"  ❌ Validation failed for {claw_site['name']}: {e}")
            skipped += 1
            continue

        # Write
        primary = claw_site["classification"]["primary"]
        out_dir_primary = out_dir / primary
        out_dir_primary.mkdir(parents=True, exist_ok=True)
        out_path = out_dir_primary / f"{claw_site['id']}.json"
        out_path.write_text(json.dumps(claw_site, indent=2, ensure_ascii=False))
        migrated += 1

    print(f"\nDone: {migrated} migrated, {skipped} skipped")
    print(f"Output: {out_dir}/")


if __name__ == "__main__":
    main()
