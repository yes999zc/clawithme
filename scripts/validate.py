#!/usr/bin/env python3
"""Validate all site JSON files against the schema."""

import json
import sys
from pathlib import Path

from jsonschema import ValidationError, validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "data" / "schema.json"
SITES_DIR = ROOT / "data" / "sites"


def main():
    schema = json.loads(SCHEMA_PATH.read_text())
    errors = []
    ok = 0

    for json_file in SITES_DIR.rglob("*.json"):
        if "migrated" in str(json_file):
            continue
        try:
            site = json.loads(json_file.read_text())
            validate(site, schema)
            ok += 1
        except ValidationError as e:
            errors.append((json_file.name, str(e)))
        except json.JSONDecodeError as e:
            errors.append((json_file.name, f"Invalid JSON: {e}"))

    print(f"Validated: {ok} OK, {len(errors)} errors")
    if errors:
        for name, err in errors:
            print(f"  ❌ {name}: {err}")
        sys.exit(1)
    else:
        print("✅ All sites valid")


if __name__ == "__main__":
    main()
