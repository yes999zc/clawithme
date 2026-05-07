# STATE.md — clawithme

Last updated: 2026-05-07 (night — all fixes verified, uv cache cleared)

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
| Incremental search | ✅ (stale cache reuse, 14s → 2s for repeats) |
| Watch/monitoring | ✅ (periodic re-scan + change detection + webhook) |
| LinkedIn auth | ✅ (cookie-based Playwright login + deep extraction) |
| Tiered proxy | ✅ (direct/datacenter/residential + Admin UI) |
| Site health | ✅ (verify --auto-fix + Admin health dashboard) |
| Actionable reports | ✅ (5 recommendation types in report footer) |
| Demo page | ✅ (GitHub Pages, 3 persona tabs, Geist design) |
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
| **11** | **Infrastructure fixes — cache, timeout, proxy, LinkedIn, watch, incremental** | ✅ |
| **12** | **Site health, actionable reports, persona landing page** | ✅ |
| — | Vercel deployment | ❌ cancelled (user purchasing server) |
| — | Proxy pool rotation | ⏸️ deferred (tiered proxy foundation ready) |
| — | Open-core model evaluation | ⏸️ deferred |

## Architecture

```
clawithme/                          # Monorepo — all 49 extractors unified
├── cli.py                          # CLI entry (sync + async)
├── pipeline.py                     # AsyncPipeline — orchestrator
├── config.py                       # Config + API keys from env
├── cache.py                        # SQLite TTL cache (WAL mode)
├── logging.py                      # structlog
├── engine/
│   ├── engines.py                  # 9 detection engines
│   ├── loader.py                   # load from engines.json
│   ├── http_client.py              # Scrapling DynamicFetcher
│   └── proxy_manager.py            # Per-tier HttpClient pool
├── crawler/
│   ├── base.py                     # Profile, ProfileExtractor ABC
│   ├── client.py                   # CrawlerClient
│   ├── registry.py                 # discover_extractors() via entry_points
│   └── extractors/                 # 49 extractors (CN + international combined)
├── signals/
│   ├── correlation.py              # CorrelationEngine + Cluster
│   ├── avatar.py                   # pHash + default avatar filter
│   └── llm_verifier.py             # Multi-provider LLM identity scoring
├── leak_sources/
│   ├── manager.py                  # Parallel breach query
│   ├── cavalier.py                 # Cavalier infostealer DB
│   └── hibp.py                     # HaveIBeenPwned API
├── report/
│   ├── i18n.py                     # Bilingual strings + constants
│   ├── template.py                 # Geist HTML template
│   ├── renderers.py                # All _render_*() helper functions
│   └── generator.py                # HTML + JSON + PDF + Markdown export
├── web/
│   ├── app.py                      # FastAPI + SSE streaming (lifespan)
│   ├── routes/
│   │   ├── report.py               # Report download API endpoint
│   │   └── admin.py                # Proxy config management API
│   └── static/
│       ├── index.html              # Geist frontend (i18n, search params, clusters)
│       └── admin.html              # Proxy tier management page
├── data/
│   ├── sites/                      # 44 curated site JSONs
│   ├── sites/migrated/             # 2,487 migrated site JSONs
│   └── schema.json                 # JSON Schema
└── webui.sh                        # One-command launcher script
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
- **All extractors in main repo** — `clawithme-cn` plugin repo [archived](https://github.com/yes999zc/clawithme-cn); all 49 extractors live in monorepo
- **Error-aware caching** — probe failures (network errors, timeouts) are never cached; only genuine classification results are cached
- **Tiered cache TTL** — positive hits 24h, negatives 1h (to recover quickly from anti-bot false negatives like 403/429)
- **Per-request timeout** — `HttpClient.get()` accepts optional `timeout_ms`; engine resolves site → engine → config priority chain
- **Tiered proxy** — sites declare `proxy_tier` (direct/datacenter/residential); `ProxyManager` selects HttpClient per site; admin page for runtime config

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

## 2026-05-07 — 基础设施修复（cache / timeout / proxy 贯通）

### 根因：假阴性被缓存 24 小时

`Engine.probe()` 内部 catch 网络异常后返回 `EngineResult(exists=False, error="...")`，
但 `AsyncPipeline._probe_one()` 和 `_search_sync()` 不检查 `result.error` 字段，
将所有 `exists=False` 一律缓存为「用户不存在」，TTL 24h。
一次瞬态网络故障 → 该站点 24h 内不再探测。

### 修复清单

| 文件 | 改动 |
|------|------|
| `engine/engines.py` | 探测超时从硬编码 5000ms → 优先站点 `check.timeout_ms` / 引擎 `params.timeout_ms`；异常日志 error→warning |
| `engine/http_client.py` | `get()` 支持 `timeout_ms` 参数按请求覆盖 |
| `engine/loader.py` | `load_engines()` 接受可选 `HttpClient` 参数（为 proxy 贯通做准备） |
| `pipeline.py` | `_probe_one()`：`result.error` 不为 None 时不缓存；阴性结果 TTL 从 24h → 1h |
| `cli.py` | 同步路径同样修复：不缓存异常结果 + 阴性 TTL 1h；贯通 proxy → HttpClient |
| `web/app.py` | 两处 `load_engines()`：从 config 创建带 proxy 的 HttpClient |
| `tui/screens/results.py` | 同样贯通 proxy 配置 |
| `config.example.toml` | Proxy 配置格式说明和示例 |

### 防护层级

| 场景 | 之前 | 现在 |
|------|------|------|
| 网络超时/DNS失败/连接拒绝 | 缓存为「不存在」24h | **不缓存**，下次重新探测 |
| 引擎判定「用户不存在」 | 缓存 24h | 缓存 **1h**（403/429 误判可快速恢复） |
| 引擎判定「用户存在」 | 缓存 24h | 缓存 24h（不变） |

### Proxy 贯通

`config.toml` → `Config.proxy` → `HttpClient(proxy=...)` → `load_engines(http_client=...)` → 所有 Engine 共享同一 HttpClient → 所有站点探测走代理。

基础设施已就位：`ProxyConfig`（config.py）、`HttpClient(proxy=)`（http_client.py）、
`Engine(http_client=)`（engines.py）三层早已支持，此前只是没有接通。

## 2026-05-07 — Phase 11+12 交付物

### Phase 11：基础设施修复 + 品质功能
| 功能 | 说明 |
|------|------|
| 缓存假阴性修复 | 探测失败不再缓存为「不存在」，阴性 TTL 24h→1h |
| 超时贯通 | 站点/引擎 timeout 配置真正生效 |
| 分级代理 | `proxy_tier` + ProxyManager + Admin 管理后台 |
| `linkedin-login` | 交互式浏览器登录，Cookie 自动保存 |
| LinkedIn 深度提取 | Cookie + Playwright，探测+提取双阶段 |
| `clawithme watch` | 定时监控 + 基准对比 + 变更检测 + webhook |
| `--incremental` | 增量搜索，重用过期缓存，14s→2s |
| Demo 页面 | GitHub Pages，Geist 风格，3 用户画像 |

### Phase 12：品质路线图（P0+P1+P2）
| 功能 | 说明 |
|------|------|
| 站点健康自愈 | `verify_site.py --auto-fix`，Admin 面板展示 |
| 报告可操作建议 | 5 类自动建议（泄露/头像/空白账号/曝光/用户名） |
| 差异化 Landing | 安全研究员 / 隐私个人 / HR 背调 3 条路径 |

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
