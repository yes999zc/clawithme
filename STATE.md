# STATE.md — clawithme

Last updated: 2026-05-06

## Quick Stats

| Metric | Value |
|--------|-------|
| HEAD | `0b06346` (main, aligned with GitHub) |
| Python lines | ~8,400 |
| Tests | **243 passed**, 5 skipped (WeasyPrint system deps) |
| Ruff | 0 on Phase 8 files; 9 pre-existing in extractors/engine |
| Curated sites | 44 |
| Migrated sites | 2,487 |
| Detection engines | 9 |
| Profile extractors | **49** (was 34) |
| Async pipeline | 10-concurrent, cold ~14s (was 180s) |
| Hit confidence scoring | ✅ (0.0-1.0 with name/field/Script checks) |
| Wrong-person detection | ✅ (Levenshtein + CJK script filter) |

## Phase Status

| Phase | Deliverable | Status |
|:---:|------|:---:|
| 1 | Site probing (9 engines, SearXNG fallback) | ✅ |
| 2 | Profile extraction (43 extractors) | ✅ |
| 3 | Leak database (Cavalier + HIBP) | ✅ |
| 4 | Multi-signal correlation (Union-Find + anti-merge) | ✅ |
| 5 | HTML/JSON report (Geist design) | ✅ |
| 6 | LLM Verifier (DeepSeek/Kimi/百炼) + SQLite cache | ✅ |
| 7 | Async pipeline (asyncio.gather, 10 concurrent) | ✅ |
| 8 | Web UI (FastAPI + SSE) + PDF (WeasyPrint) | ✅ |
| — | 天眼查 API | ❌ cancelled |
| — | Vercel deployment | ❌ cancelled (user purchasing server) |
| 9a | P0 extractors — Instagram/Twitter/Weibo/Sspai/Twitch/SlideShare | ✅ |
| 9b | P1 extractors — Zhihu/Gitee/Tieba/WordPress/Blogger | ✅ |
| 9c | Hit confidence scoring + wrong-person detection | ✅ |
| 9d | Stack Overflow probe fix (hardcoded UID removed) | ✅ |
| 9e | Report UX — confidence badges, identity assessment card | ✅ |
| 9f | P2 extractors — LeetCode/Goodreads/Chess/CodePen/Discogs/Hupu | ✅ |
| 10 | TBD — server deployment | 🔜 next |

## Architecture

```
clawithme/
├── cli.py              # CLI entry (sync + async)
├── pipeline.py         # AsyncPipeline — orchestrator
├── config.py           # Config + API keys from env
├── cache.py            # SQLite TTL cache (WAL mode)
├── logging.py          # structlog
├── engine/
│   ├── engines.py      # 9 detection engines
│   ├── loader.py       # load from engines.json
│   └── http_client.py  # Scrapling DynamicFetcher
├── crawler/
│   ├── base.py         # Profile, ProfileExtractor
│   ├── client.py       # CrawlerClient
│   ├── registry.py     # discover_extractors()
│   └── extractors/     # 43 profile extractors
├── signals/
│   ├── correlation.py  # CorrelationEngine + Cluster
│   ├── avatar.py       # pHash + default avatar filter
│   └── llm_verifier.py  # Multi-provider LLM identity scoring
├── leak_sources/
│   ├── manager.py      # Parallel breach query
│   ├── cavalier.py     # Cavalier infostealer DB
│   └── hibp.py         # HaveIBeenPwned API
├── report/
│   └── generator.py    # HTML + JSON + PDF export (WeasyPrint)
├── web/
│   ├── app.py          # FastAPI + SSE streaming
│   └── static/
│       └── index.html  # Geist frontend
└── data/
    ├── sites/          # 44 curated site JSONs
    ├── sites/migrated/ # 2,487 migrated site JSONs
    └── schema.json     # JSON Schema
```

## Key Design Decisions

- **No local LLM** — multi-provider API only (DeepSeek/Kimi/百炼)
- **No Docker for dev** — pip install -e ".[web]"
- **SSE over WebSocket** — simpler, no upgrade dance
- **SQLite WAL + check_same_thread=False** — safe for async reads
- **Anti-merge gate** — username-only match requires additional signal
- **Provider-agnostic LLM** — `LLMProvider` dataclass, auto-discover
- **Playwright disabled by default** — only 4/43 extractors need it
- **Path traversal protection** — `_write_report()` validates cwd containment
- **Confidence scoring over binary classification** — hits get 0.0-1.0 based on HTTP status, SPA flag, extractor data, display_name match, field completeness
- **Wrong-person detection** — Levenshtein similarity + CJK script detection to avoid false flags on Chinese names

## New in Phase 9

### Confidence Scoring System
- Replaced old 3-tier (confirmed/uncertain/dropped) with continuous 0.0-1.0 scoring
- `_compute_hit_confidence()`: SPA+extractor_data=0.80, non-SPA 200=0.85, no extractor=0.40
- `_is_wrong_person()`: catches cases like "Jon Skeet" returned for search "oadank"
- Report shows "确认" (green), "待验证" (amber), "低置信" (red) badges per hit

### New Extractors (43 total, up from 32)
- **P0 (SPA sites)**: Instagram (og:meta), Twitter/X (dynamic Playwright), Weibo (static HTML), 少数派 (dynamic Playwright), Twitch (meta tags), SlideShare (static HTML)
- **P1**: 知乎 (REST API), Gitee (REST API), 贴吧 (static HTML), WordPress.com (og:meta), Blogger (og:meta)

### Bug Fixes
- Stack Overflow probe no longer hardcodes user ID 22656 (Jon Skeet)
- Instagram og:title regex correctly extracts Chinese display names
- Twitter extractor fixed to use dynamic fetch + `__INITIAL_STATE__` JSON parsing

## APIs Configured

| Provider | Env Var | Endpoint |
|----------|---------|----------|
| DeepSeek | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` |
| DashScope (Coding Plan) | `DASHSCOPE_API_KEY` | `https://coding.dashscope.aliyuncs.com/v1` |
| Kimi | `KIMI_API_KEY` | `https://api.moonshot.cn/v1` |
| HIBP | `HIBP_API_KEY` | `https://haveibeenpwned.com/api/v3` |

## Hosting (planned)

- Target: 4C8G HK VPS, ~¥108/mo
- Stack: Python 3.11 + uvicorn + nginx
- No Docker, no GPU
- Provider shortlist: 腾讯云轻量 HK > 阿里云 HK > Vultr HK

## Known Issues (pre-existing, not blocking)

- 9 ruff violations in extractors/engine (PLC0415, F401, E501)
- Bilibili extractor: `import urllib.parse` at function level
- `keybase.py`: E501 line too long
- `http_client.py`: `from scrapling import Fetcher` at init level
- WeasyPrint missing `libgobject-2.0-0` in Hermes venv (CLI works with `DYLD_LIBRARY_PATH`)
