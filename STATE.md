# STATE.md — clawithme

Last updated: 2026-05-07

## Quick Stats

| Metric | Value |
|--------|-------|
| HEAD | `main` (local ahead) |
| Python lines | ~9,200 |
| Tests | **243 passed**, 5 skipped (WeasyPrint system deps) |
| Ruff | 0 on Phase 8 files; 9 pre-existing in extractors/engine |
| Curated sites | 44 |
| Migrated sites | 2,487 |
| Detection engines | 9 |
| Profile extractors | **49** |
| Async pipeline | 10-concurrent, cold ~14s (was 180s) |
| Report formats | HTML + JSON + PDF + **Markdown** |
| WebUI i18n | zh + **en** |
| Hit confidence scoring | ✅ (0.0-1.0 with name/field/Script checks) |
| Wrong-person detection | ✅ (Levenshtein + CJK script filter) |

## Phase Status

| Phase | Deliverable | Status |
|:---:|------|:---:|
| 1 | Site probing (9 engines, SearXNG fallback) | ✅ |
| 2 | Profile extraction (43 → 49 extractors) | ✅ |
| 3 | Leak database (Cavalier + HIBP) | ✅ |
| 4 | Multi-signal correlation (Union-Find + anti-merge) | ✅ |
| 5 | HTML/JSON/PDF report (Geist design) | ✅ |
| 6 | LLM Verifier (DeepSeek/Kimi/百炼) + SQLite cache | ✅ |
| 7 | Async pipeline (asyncio.gather, 10 concurrent) | ✅ |
| 8 | Web UI (FastAPI + SSE) + PDF (WeasyPrint) | ✅ |
| 9a–9f | Extractor expansion + confidence scoring | ✅ |
| **10a** | **SSE data enrichment — all fields streamed** | ✅ |
| **10b** | **Frontend rewrite — search params, i18n, cluster UX** | ✅ |
| **10c** | **Report download API — HTML/JSON/PDF/MD** | ✅ |
| **10d** | **Evidence UX — site-pair info, dedup, plain language** | ✅ |
| **10e** | **WebUI i18n — zh/en language switch** | ✅ |
| — | 天眼查 API | ❌ cancelled |
| — | Vercel deployment | ❌ cancelled (user purchasing server) |

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
│   └── extractors/     # 49 profile extractors
├── signals/
│   ├── correlation.py  # CorrelationEngine + Cluster
│   ├── avatar.py       # pHash + default avatar filter
│   └── llm_verifier.py  # Multi-provider LLM identity scoring
├── leak_sources/
│   ├── manager.py      # Parallel breach query
│   ├── cavalier.py     # Cavalier infostealer DB
│   └── hibp.py         # HaveIBeenPwned API
├── report/
│   ├── i18n.py         # Bilingual strings + constants
│   ├── template.py     # Geist HTML template
│   ├── renderers.py    # All _render_*() helper functions
│   └── generator.py    # HTML + JSON + PDF + Markdown export
├── web/
│   ├── app.py          # FastAPI + SSE streaming (lifespan)
│   ├── routes/
│   │   └── report.py   # Report download API endpoint
│   └── static/
│       └── index.html  # Geist frontend (i18n, search params, clusters)
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
- **Playwright disabled by default** — only 4/49 extractors need it
- **Path traversal protection** — `_write_report()` validates cwd containment
- **Confidence scoring over binary classification** — hits get 0.0-1.0
- **Wrong-person detection** — Levenshtein + CJK script filter
- **Evidence with site pairs** — every evidence string includes `siteA ↔ siteB: value`
- **WebUI i18n via data-i18n** — HTML attribute-driven, runtime switchable
- **DYLD_LIBRARY_PATH auto-fix** — macOS/Homebrew WeasyPrint path handled in main()

## New in Phase 10

### SSE Data Enrichment
- Hit events: +status, +category, +confidence, +wrong_person
- Profile events: all 13 fields (was 6) — email, phone, joined_date, post_count, following_count, extra
- Cluster events: +evidence (with site-pair info), +profile_count
- New `leak` event: individual BreachRecord streaming
- New `leakstatus` event: per-source counts before stream
- Pre-pipeline phase event: user sees "scanning..." during pipeline execution
- Done event: +sources_used, +llm_configured

### Frontend Rewrite
- Search parameters panel: migrated, no_cache, sync, lang
- Search type auto-detect (email/phone/username)
- Real-time stats bar (all 6 counters)
- Site hits: by category, confidence badges, wrong-person warnings
- Profile cards: completeness donut, all fields, collapsible detail table
- Cluster cards: evidence dedup+summarize, site-pair display, plain-language signals, standalone profiles
- Leak records section: per-source grouping, redacted display
- Report download buttons (HTML/JSON/PDF/MD)
- Cancel button for long searches
- `Cache-Control: no-cache` on index page

### Evidence UX Overhaul
- Evidence strings include `siteA ↔ siteB: value` pair info (backend correlation.py)
- Username dedup: "All N profiles share the same username" instead of N*(N-1)/2 lines
- Signal → plain language mapping (e.g. "avatar_phash" → "🖼 Avatar images appear visually similar")
- Standalone profiles section: "👤 twitter — No cross-platform match found"
- Confidence → readable labels: "Very likely same person (92%)"

### WebUI i18n
- Full _STRINGS zh/en dictionary (~60 keys)
- Language toggle in page header (中文 | EN)
- `data-i18n` attributes on all static text
- Language follows through to report download (lang query param)
- Report language can be overridden at download time

### Report Download API
- `GET /api/report/{trace_id}?format=html|json|pdf|md&username=xxx&lang=zh|en`
- In-memory result cache (5 min TTL)
- Markdown report: export_markdown() with site table, profile details, clusters, leaks

### CLI Dedup
- `_print_search_results()` — shared output for 3 callers
- `_write_search_report()` — shared report write for 3 callers
- `_query_all_leaks()` — shared leak query for 3 callers
- `_search_leaks` 120→47 lines, `_search_sync` 133→31 lines, `_search_async` 116→21 lines

### Infrastructure
- `@app.on_event` → `lifespan` context manager (removes FastAPI deprecation warning)
- `@app.on_event("shutdown")` closes SQLite cache connection
- Dead config removed: `dehashed_api_key`, `dehashed_email`
- DYLD_LIBRARY_PATH auto-set for macOS/Homebrew WeasyPrint
- `webui.sh` launcher script
- TUI banner (Hermes-style full-width header)

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
- WeasyPrint missing `libgobject-2.0-0` in Hermes venv (CLI works with built-in DYLD fix)
- Scrapling Fetcher: "use Fetcher.configure() instead" warning (library deprecation, no functional impact)
