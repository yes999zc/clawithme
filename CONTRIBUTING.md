# Contributing to clawithme

Thanks for contributing! This guide helps you add new site definitions.

## Quick Start

1. Fork the repo and clone it
2. Install dev dependencies: `pip install -e ".[dev]" jsonschema`
3. Add your site JSON file
4. Validate: `python scripts/validate.py`
5. Submit PR

## Adding a New Site

### Step 1: Find a test account

You need at least one **known existing** account and one **known non-existing** username to validate the detection rule.

### Step 2: Determine the probe URL

Find the URL pattern for user profiles. Replace the username with `{username}`:

```
https://example.com/users/{username}
https://api.example.com/v1/user/{username}
```

### Step 3: Create the JSON file

Create a file at `data/sites/<primary>/<site_id>.json` using this template:

```json
{
  "id": "example",
  "name": "Example Site",
  "canonical_url": "https://example.com/{username}",
  "engine_ref": "base_http_status",
  "classification": {
    "primary": "social",
    "identity_type": "virtual_social",
    "geo_region": "global",
    "user_scale": 1000000,
    "tags": ["example-tag"]
  },
  "rankings": {},
  "check": {
    "probe_url": "https://example.com/api/user/{username}",
    "expected": 200,
    "known_accounts": ["realuser123"],
    "known_unclaimed": ["thisuserdoesnotexist99999"]
  },
  "nsfw": false,
  "deprecated": false,
  "source": "community",
  "last_updated": "2026-05-04T00:00:00Z"
}
```

### Field Reference

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Unique slug (lowercase, hyphens) |
| `name` | ✅ | Human-readable site name |
| `canonical_url` | ✅ | Public profile URL with `{username}` |
| `engine_ref` | ✅ | Engine name from `data/engines.json` |
| `classification.primary` | ✅ | Category: social/devtools/forum/media/ecommerce/gaming/music/blog/academic |
| `classification.identity_type` | ✅ | real_social / public_social / virtual_social / anonymous / professional |
| `classification.geo_region` | ✅ | cn / asia / europe / americas / global |
| `check.probe_url` | ✅ | URL to probe for existence check |
| `check.known_accounts` | 🟡 | Known existing accounts (for validation) |
| `check.known_unclaimed` | 🟡 | Known non-existing usernames (for false-positive detection) |
| `check.expected` | — | Expected HTTP status code (default: 200) |

### Classification Guide

- **identity_type**:
  - `real_social` — Requires real identity (WeChat, LinkedIn)
  - `public_social` — Semi-real, searchable publicly (Weibo, Xiaohongshu)
  - `virtual_social` — Pseudonymous, interest-driven (Bilibili, Zhihu)
  - `anonymous` — Fully anonymous (Tieba, imageboards)
  - `professional` — Career/portfolio (GitHub, Juejin)

- **geo_region**:
  - `cn` — China mainland
  - `asia` — Asia (excl. China)
  - `europe`, `americas` — Regional
  - `global` — No dominant region

## Validation

```bash
# Validate all site JSONs against schema
python scripts/validate.py

# Test a single site detection rule
python scripts/verify_site.py <site_id>

# Run all site verifications
python scripts/verify_site.py --all

# View database statistics
python scripts/stats.py
```

### Choosing known_accounts

Every active site MUST have at least one `known_accounts` entry. These are used by CI to verify detection rules haven't degraded.

**Requirements for known_accounts:**

| Requirement | Why |
|-------------|-----|
| Public profile, not private | Must be accessible without login |
| Stable account (not likely deleted) | CI runs daily — broken account = false alarm |
| Verified via HTTP probe | Run `scripts/verify_site.py <site_id>` to confirm |
| 1–2 accounts per site | One is enough; two provides redundancy |

**Requirements for known_unclaimed:**

| Requirement | Why |
|-------------|-----|
| Definitely doesn't exist | CI checks that the rule correctly rejects nonexistent users |
| Random/unique username | Avoid collisions with real users who might register later |
| Same length pattern as real usernames | Some sites behave differently for short vs long usernames |

### Site verification workflow

```bash
# 1. After adding a site JSON, run verification
python scripts/verify_site.py <site_id>

# 2. Expected output:
#    ✅ HEALTHY  Example Site (example)  engine=base_http_status  classifier=status_code
#             2/2 checks passed
#      ✅ known_existing: realuser123 → 200
#      ✅ known_unclaimed: nonexistent_xyz → 404

# 3. If you see ⚪ NO CHECKS — known_accounts is empty, fill them
# 4. If you see ❌ DEGRADED — detection rule is broken, fix the engine or check config
```

## CI Checks

All PRs are automatically checked for:
- JSON Schema validation (`python scripts/validate.py`)
- Site statistics (`python scripts/stats.py`)
