# clawithme

<p align="center">
  <a href="https://clawith.me"><img src="https://img.shields.io/badge/Web%20UI-clawith.me-16a34a?style=flat-square&labelColor=171717"/></a>
  <a href="https://pypi.org/project/clawithme/"><img src="https://img.shields.io/pypi/v/clawithme?style=flat-square&labelColor=171717&color=16a34a"/></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-808080?style=flat-square&labelColor=171717"/></a>
  <a href="https://github.com/yes999zc/clawithme/actions"><img src="https://img.shields.io/github/actions/workflow/status/yes999zc/clawithme/ci.yml?style=flat-square&labelColor=171717&color=16a34a"/></a>
</p>

<p align="center">
  <b>OSINT identity panorama scanner.</b><br>
  Enter a username, email, or phone — discover presence across 3,200+ platforms,<br>
  correlate identities, and export professional reports.
</p>

<p align="center">
  <a href="https://clawith.me"><b>Try the Web UI →</b></a>
</p>

---

## Overview

clawithme scans global platforms — from social networks and developer communities to Chinese forums and e-commerce sites — for a given identity signal, then cross-correlates the results to build a unified identity panorama.

| Stage | What it does |
|-------|-------------|
| **Probe** | 3,200+ sites across 9 detection engines (HTTP status, body markers, CMS fingerprinting) |
| **Extract** | 49 platform-specific extractors: GitHub, Zhihu, LinkedIn, HackerNews, Douban, etc. |
| **Leak Check** | Cavalier infostealer records + HIBP breach database, parallel query |
| **Correlate** | Multi-signal identity clustering: email, phone, avatar pHash, username similarity |
| **Verify** | LLM-based confidence scoring across DeepSeek / Kimi / 百炼 |
| **Report** | Self-contained HTML / PDF / JSON / Markdown export |

---

## Quick Start

```bash
# Via Docker
docker pull ghcr.io/yes999zc/clawithme
docker run -p 8000:8000 ghcr.io/yes999zc/clawithme

# Open http://localhost:8000

# CLI usage
docker run ghcr.io/yes999zc/clawithme \
  clawithme search <username> --acknowledge-ethical-use

# Generate a report
docker run ghcr.io/yes999zc/clawithme \
  clawithme search <username> \
  --report report.html --acknowledge-ethical-use
```

```bash
# Via PyPI
pip install clawithme[web]
clawithme-web                    # → http://localhost:8000
clawithme search <username> --acknowledge-ethical-use
```

```bash
# From source
git clone https://github.com/yes999zc/clawithme.git
cd clawithme
pip install -e ".[dev]"
clawithme search <username> --acknowledge-ethical-use
```

---

## Features

- **3,200+ sites** — curated probes + migrated dataset, engine-classified
- **9 detection engines** — status code, body markers, headers; CMS: XenForo, Discourse, phpBB, vBulletin, WordPress, Discuz!
- **49 profile extractors** — GitHub, Zhihu, Reddit, LinkedIn, HackerNews, Douban, Juejin, NGA, Steam, and more
- **Async pipeline** — 10-concurrent `asyncio.gather`, cold search 180s → 14s
- **Leak database** — Cavalier infostealer + HIBP, parallel with graceful degradation
- **LLM verification** — DeepSeek / Kimi / 百炼 multi-provider, structured confidence scoring
- **Identity clustering** — Union-Find transitive closure across email, phone, pHash, username; anti-merge gate
- **Professional reports** — Geist-designed HTML, PDF via WeasyPrint, grayscale aesthetic, PII-redacted
- **Web UI** — FastAPI + SSE streaming, Geist frontend, zero-config deploy
- **Paid API integrations** — Douyin / Xiaohongshu / LinkedIn via TikHub (optional, opt-in)

---

## Usage

```bash
# Basic search (curated sites)
clawithme search <username> --acknowledge-ethical-use

# Full search (all 3,200+ sites)
clawithme search <username> --include-migrated --acknowledge-ethical-use

# Report formats
clawithme search <username> --report report.html --acknowledge-ethical-use
clawithme search <username> --report report.pdf --format pdf --acknowledge-ethical-use
clawithme search <username> --report report.json --format json --acknowledge-ethical-use
clawithme search <username> --report report.md --format md --acknowledge-ethical-use

# Validation & stats
python scripts/validate.py
python scripts/verify_site.py --all
python scripts/stats.py

# Tests
pytest tests/ -v
```

---

## Architecture

```
┌─ Input ─────────────────────────────┐
│  username / email / phone           │
└──────────────────┬──────────────────┘
                   ▼
┌─ Phase 1: Probe ───────────────────┐
│  3,200+ sites · 9 engines          │
│  Scrapling fingerprinting          │
│  SearXNG fallback                  │
└──────────────────┬──────────────────┘
                   ▼
┌─ Phase 2: Extract ─────────────────┐
│  49 platform extractors            │
│  CSS/XPath · Playwright            │
│  Avatar pHash                      │
└──────────────────┬──────────────────┘
                   ▼
┌─ Phase 3: Leak Check ──────────────┐
│  Cavalier + HIBP (parallel)        │
└──────────────────┬──────────────────┘
                   ▼
┌─ Phase 4: Correlate ───────────────┐
│  Multi-signal Union-Find           │
│  email(1.0)·phone(0.95)·pHash(0.8)│
│  ·username(0.7)                    │
└──────────────────┬──────────────────┘
                   ▼
┌─ Phase 5: Verify ──────────────────┐
│  LLM provider-agnostic verifier    │
│  Structured confidence output      │
└──────────────────┬──────────────────┘
                   ▼
┌─ Phase 6: Report ──────────────────┐
│  HTML / PDF / JSON / Markdown      │
│  Identity clusters · PII redaction │
│  Breach timeline · Distribution    │
└────────────────────────────────────┘
```

---

## vs Maigret

| | maigret | clawithme |
|---|---------|-----------|
| **Site storage** | Monolithic `data.json` | One JSON per site + JSON Schema |
| **Detection** | Hardcoded ~1,200 lines | 9 pluggable engines |
| **HTTP layer** | aiohttp + requests | Scrapling (curl_cffi fingerprinting) |
| **Deep extraction** | Plugin-based | Built-in extractors (GitHub, Zhihu, etc.) |
| **Leak database** | None | Cavalier + HIBP, parallel |
| **Identity correlation** | None | Union-Find: email/phone/avatar/username |
| **Quality gate** | None | CI: daily verification + Schema + Ruff |
| **Chinese platforms** | Limited | 16+ CN platforms + Discuz! engine |

---

## Ethical Use

**This tool queries public profiles and breach databases. Use only on accounts you own or have explicit authorization to investigate.** Unauthorized use may violate platform Terms of Service, privacy regulations (GDPR, PIPL), and ethical norms.

The CLI enforces an `--acknowledge-ethical-use` flag. The Web UI requires an ethics checkbox before each search.

---

## License

MIT
