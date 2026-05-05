# TODO.md — clawithme Roadmap

Last updated: 2026-05-06

## ✅ Completed (Phase 1–8)

| Phase | Item | Commit |
|:---:|------|--------|
| 1 | Site probing — 9 engines, SearXNG fallback | — |
| 2 | Profile extraction — 34 extractors (GitHub, Zhihu, Reddit, ...) | — |
| 3 | Leak database — Cavalier + HIBP, parallel manager | — |
| 4 | Multi-signal correlation — Union-Find + anti-merge gate | — |
| 5 | HTML/JSON report — Geist design, auto-summary, charts | — |
| 6 | LLM Verifier — DeepSeek/Kimi/百炼, SQLite cache, CI/CD | — |
| 7 | Async pipeline — 10-concurrent, 180s→14s | — |
| 8 | Web UI — FastAPI + SSE + Geist frontend | `45a869a` |
| 8 | PDF export — WeasyPrint (same Geist HTML) | `868ecf5` |
| 8 | Phase 8 audit — 6 fixes, 13 new tests | `290a41e` |
| — | README + STATE.md docs | `0fce64f` `94c519a` |
| ❌ | 天眼查 API | cancelled |
| ❌ | Vercel deployment | cancelled (user purchasing server) |

## 🔜 Phase 9 — Expansion (next)

| ID | Item | Est. |
|----|------|:---:|
| 9a | International extractors — Twitter/X, Instagram, TikTok, Facebook | 16h |
| 9b | CN extractors — 微博, 小红书, 抖音, 贴吧 | 16h |
| 9c | SearXNG integration — multi-engine fallback for missed sites | 8h |
| 9d | Profile enrichment — cross-platform data merge, dedup | 12h |
| 9e | Email → platform resolution — find accounts by email | 8h |
| 9f | Server deployment — uvicorn + nginx + systemd | 8h |

## 📋 Backlog

| ID | Item | Est. |
|----|------|:---:|
| B1 | Vercel serverless (revisit if timeout limit changes) | 8h |
| B2 | Image-to-identity — avatar reverse search | 24h |
| B3 | Phone → platform — carrier lookup + SMS verification check | 16h |
| B4 | Multi-language report — i18n for CN/EN | 8h |
| B5 | Playwright pool — shared browser instances for dynamic sites | 12h |
| B6 | Rate-limit middleware — per-IP/user throttling | 4h |
| B7 | Auth + multi-tenant — login, API keys, usage tracking | 24h |
| B8 | Discord/Telegram bot — remote search via chat | 12h |
| B9 | Graph visualization — D3.js identity cluster graph | 8h |
| B10 | Leak DB expansion — additional breach sources | 16h |

## Known Debt

| ID | Item | Severity |
|----|------|:---:|
| D1 | 9 pre-existing ruff violations in extractors/engine | 🟢 |
| D2 | WeasyPrint system deps missing in Hermes venv | 🟢 |
| D3 | No Playwright concurrency tests | 🟡 |
| D4 | `_render_profiles` 78 statements — needs refactor | 🟡 |
| D5 | 天眼查 stub extractor still registered (no-op) | 🟡 |
