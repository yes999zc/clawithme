# clawithme

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue?style=flat-square)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![CI](https://github.com/yes999zc/clawithme/actions/workflows/ci.yml/badge.svg)](https://github.com/yes999zc/clawithme/actions/workflows/ci.yml)
[![tests](https://img.shields.io/badge/tests-160%20passed-brightgreen?style=flat-square)](https://github.com/yes999zc/clawithme/actions)

**Username to identity panorama — for the Chinese internet and beyond.**

</div>

---

Input a username. Discover their presence across 3000+ platforms — from social networks to dev communities, from Chinese local forums to global sites. Link identities through email, phone, avatar hashes, and leaked credentials. Export a self-contained Geist-style HTML report.

## Quick Start

```bash
pip install -e ".[dev]"
clawithme search <username> --acknowledge-ethical-use
clawithme search <username> --report report.html --acknowledge-ethical-use
```

## Pipeline

```
username
  |
  +-- Phase 1: Site probing (36 curated + 2487 migrated, 9 CMS engines)
  |     |
  |     +-- HTTP status code / body message / header matching
  |     +-- Scrapling anti-bot fingerprinting
  |     +-- SearXNG fallback for un-hit sites
  |
  +-- Phase 2: Profile extraction (GitHub, Zhihu extractors)
  |     +-- CSS/XPath selectors, Playwright for JS-rendered pages
  |     +-- Avatar perceptual hash (pHash)
  |
  +-- Phase 3: Leak database query (Cavalier + HIBP, parallel manager)
  |
  +-- Phase 4: Multi-signal correlation
  |     +-- email (1.0) · phone (0.95) · avatar pHash (0.8) · username (0.7)
  |     +-- Union-Find transitive closure
  |
  +-- Phase 5: Geist HTML report
        +-- Platform distribution charts
        +-- Breach timeline
        +-- Identity clusters with confidence badges
        +-- PII redaction
```

## Features

- **9 detection engines** — status code, body message, headers, plus XenForo/Discourse/phpBB/vBulletin/WordPress/Discuz! CMS
- **3000+ sites** — 36 hand-curated + 2487 migrated from maigret_china, all engine-assigned
- **Deep extraction** — GitHub and Zhihu profile scraping with CSS selectors
- **Leak database** — Cavalier infostealer records + HIBP breach database, parallel query with graceful degradation
- **Identity correlation** — Union-Find clustering across email, phone, avatar hash, and username similarity
- **Geist report** — self-contained HTML, grayscale design, CSS-only charts, PII redacted
- **Plugin architecture** — CN site extractors via `entry_points`, main repo stays jurisdiction-clean
- **Schema-first** — JSON Schema validation on every site definition, CI-enforced
- **CI/CD** — PR schema validation + daily site verification

## vs maigret

| | maigret | clawithme |
|---|---------|-----------|
| Site storage | Monolithic `data.json` | One JSON per site + JSON Schema |
| Detection | Hardcoded ~1200 lines | 9 pluggable engines in `engines.json` |
| HTTP layer | aiohttp + requests | Scrapling (curl_cffi fingerprinting) |
| Deep extraction | socid_extractor plugin | Built-in GitHub + Zhihu extractors |
| Leak database | None | Cavalier + HIBP, parallel manager |
| Correlation | None | Union-Find: email/phone/avatar/username |
| Quality gate | None | CI: daily verify + Schema + Ruff |
| Chinese sites | Limited | 16 CN platforms + Discuz! engine |

## Installation

```bash
git clone https://github.com/yes999zc/clawithme.git
cd clawithme
pip install -e ".[dev]"
```

Requires Python 3.11+.

## Usage

```bash
# Basic search (curated 36 sites)
clawithme search yes999zc --acknowledge-ethical-use

# Full search (all 2500+ sites)
clawithme search yes999zc --include-migrated --acknowledge-ethical-use

# Generate HTML report
clawithme search yes999zc --report report.html --acknowledge-ethical-use

# Generate JSON report
clawithme search yes999zc --report report.json --format json --acknowledge-ethical-use

# Validate site database
python scripts/validate.py
python scripts/verify_site.py --all
python scripts/stats.py

# Run tests
pytest tests/ -v
```

## Ethical Use

**This tool queries public profiles and breach databases. Use only on accounts you own or have explicit authorization to investigate.** Unauthorized use may violate platform Terms of Service, privacy laws (GDPR, PIPL), and ethical norms.

The CLI enforces an `--acknowledge-ethical-use` gate.

## License

MIT
