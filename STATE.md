# STATE.md — clawithme

Last updated: 2026-05-06

## Quick Stats

| Metric | Value |
|--------|-------|
| HEAD | `0fce64f` (main, aligned with GitHub) |
| Python lines | 7,926 |
| Tests | **243 passed**, 5 skipped (WeasyPrint system deps) |
| Ruff | 0 on Phase 8 files; 9 pre-existing in extractors/engine |
| Curated sites | 44 |
| Migrated sites | 2,487 |
| Detection engines | 9 |
| Profile extractors | 34 |
| Async pipeline | 10-concurrent, cold ~14s (was 180s) |

## Phase Status

| Phase | Deliverable | Status |
|:---:|------|:---:|
| 1 | Site probing (9 engines, SearXNG fallback) | ✅ |
| 2 | Profile extraction (34 extractors) | ✅ |
| 3 | Leak database (Cavalier + HIBP) | ✅ |
| 4 | Multi-signal correlation (Union-Find + anti-merge) | ✅ |
| 5 | HTML/JSON report (Geist design) | ✅ |
| 6 | LLM Verifier (DeepSeek/Kimi/百炼) + SQLite cache | ✅ |
| 7 | Async pipeline (asyncio.gather, 10 concurrent) | ✅ |
| 8 | Web UI (FastAPI + SSE) + PDF (WeasyPrint) | ✅ |
| — | 天眼查 API | ❌ cancelled |
| — | Vercel deployment | ❌ cancelled (user purchasing server) |
| 9 | TBD — 16-24 international/CN extractor expansion | 🔜 next |

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
│   └── extractors/     # 34 profile extractors
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
- **Playwright disabled by default** — only 4/34 extractors need it
- **Path traversal protection** — `_write_report()` validates cwd containment

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
