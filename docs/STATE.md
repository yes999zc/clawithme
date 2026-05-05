# clawithme — Project State

> 2026-05-05 更新（P0 Profile 提取 5/5 + P1 Profile 提取 11/11 + 天眼查 stub）
> 源：真实代码库验证（43 .py files, 160 tests all passing, 9 engines, 19 extractors, 3119 migrated sites）

## What is clawithme

OSINT tool: username → identity panorama across platforms.
Repo: `github.com/yes999zc/clawithme` (MIT, public)
Reference projects: [maigret](https://github.com/soxoj/maigret) (25k★) + [maigret_china](https://github.com/zuo-qirun/maigret_china) — CMS engine detection logic ported; architecture is ground-up redesign.

| vs maigret/maigret_china | They | clawithme |
|---|---|---|
| Site storage | Monolithic `data.json` | One JSON per site + JSON Schema validation |
| Detection | Single `checking.py` (~1200 lines, hardcoded) | 9 pluggable Engines in `engines.json` |
| HTTP layer | aiohttp + requests | Scrapling (anti-bot fingerprinting) |
| Quality gate | None | CI: daily verify + Schema validation + Ruff 0 |
| Deep extraction | None | **19 extractors** (7 P0 + 11 P1 + 天眼查 stub) |
| Leak DB | None | Cavalier + HIBP with parallel manager |
| Correlation | None | Union-Find: email/phone/avatar_phash/username |
| Site scale | 3000+ (unverified) | 36 curated (verified) + 2487 migrated (engine-assigned) |
| CLI search | username only | username + email + phone (auto-detect) |

## Current Code State

```
~6600 lines Python, 43 .py files + tests + scripts
235 tests, all passing, Ruff 0 (by policy)
48 site JSONs (40 active, 8 deprecated), 3119 migrated sites (2487 active)
9 engines, 34 extractors
Phase 1-7 code COMPLETE. V2 Phase 1-7 DONE. Async + LLM live.
```

### Key source files

| File | Lines | Purpose |
|------|:-----:|---------|
| `clawithme/cli.py` | 520 | CLI: `search`, `verify`, `validate`. Email/phone auto-detect. SearXNG fallback. |
| `clawithme/config.py` | 109 | TOML config loader (project-root `config.toml`, not `~/.config`) |
| `clawithme/engine/http_client.py` | — | Scrapling Fetcher wrapper (lazy-imported) |
| `clawithme/engine/engines.py` | — | Engine runner + template sandbox (`str.replace`, no Jinja2) |
| `clawithme/engine/loader.py` | — | Load engines.json, match sites to engines |
| `clawithme/leak_sources/__init__.py` | 235 | BreachRecord (Pydantic, 7 fields) + LeakSource ABC + CavalierSource |
| `clawithme/leak_sources/hibp.py` | 128 | HIBP v3 API (k-anonymity, no-key graceful degradation) |
| `clawithme/leak_sources/manager.py` | 91 | LeakSourceManager: parallel Cavalier+HIBP, 15s timeout, dedup |
| `clawithme/logging.py` | — | structlog + trace_id propagation |
| `clawithme/crawler/base.py` | 72 | Profile dataclass (16 fields) + ProfileExtractor ABC |
| `clawithme/crawler/client.py` | 300 | CrawlerClient: rate limiting, UA rotation, static+dynamic fetch |
| `clawithme/crawler/registry.py` | — | Plugin discovery via `importlib.metadata` entry_points |
| `clawithme/crawler/utils.py` | — | Shared: `first_text()`, `parse_count()` |
| `clawithme/pipeline.py` | 380 | Async pipeline orchestrator (Phase 7): semaphore-bounded parallel probes + extraction |
| `clawithme/crawler/extractors/` | 19 files | See extractor table below |
| `clawithme/signals/avatar.py` | — | pHash + Hamming distance + AvatarMatch |
| `clawithme/signals/correlation.py` | 169 | Union-Find, 4-signal weighted matching |
| `clawithme/signals/extraction.py` | — | Phone regex (E.164) + email extraction + disposable filter |
| `clawithme/signals/username.py` | — | Levenshtein + compare_usernames (affix/digit patterns) |
| `clawithme/signals/llm_verifier.py` | 186 | LLM-based cluster verification (provider-agnostic, OpenAI-compatible API) |
| `clawithme/cache.py` | 92 | SQLite ResultCache with TTL, async-safe |
| `clawithme/report/generator.py` | 492 | Geist HTML + JSON export, CSS-only charts, PII redaction |
| `data/default_avatars.json` | 5 | Default avatar pHash library (GitHub identicon, forum defaults) |
| `scripts/extractor_health.py` | 132 | Weekly extractor smoke tests, breakage detection |

### Extractors (34 total)

**P0 (7 extractors) — public API-first:**

| Extractor | Method | Site | Key fields |
|-----------|--------|------|------------|
| BilibiliExtractor | API web-interface/card | bilibili.com | name, fans, gender, verified |
| V2exExtractor | API v1 members | v2ex.com | name, bio, cross-site links |
| GitlabExtractor | API v4 users | gitlab.com | name, location, twitter/linkedin |
| DevtoExtractor | API by_username | dev.to | name, bio, github/twitter |
| StackoverflowExtractor | SE 2.3 API | stackoverflow.com | name, reputation, badges |
| GithubExtractor | CSS selector | github.com | name, bio, followers, avatar_phash |
| ZhihuExtractor | Playwright | zhihu.com | (clawithme-cn plugin) |

**P1 (11 extractors) — CSS selector / API hybrid:**

| Extractor | Method | Site |
|-----------|--------|------|
| KeybaseExtractor | API | keybase.io |
| SegmentfaultExtractor | CSS | segmentfault.com |
| CsdnExtractor | CSS | blog.csdn.net |
| CoolapkExtractor | CSS | coolapk.com |
| CnblogsExtractor | CSS | cnblogs.com |
| JianshuExtractor | CSS | jianshu.com |
| HuabanExtractor | CSS | huaban.com |
| BehanceExtractor | CSS | behance.net |
| DribbbleExtractor | CSS | dribbble.com |
| FlickrExtractor | CSS | flickr.com |
| PatreonExtractor | CSS | patreon.com |

**天眼查 stub:**

| Extractor | Method | Site | Status |
|-----------|--------|------|:------:|
| TianyanchaExtractor | API (open.tianyancha.com) | 天眼查 | stub (需 token, ¥6/次) |

### Plugin: clawithme-cn

Separate repo at `~/AI_Workspace/01_Code/tools/clawithme-cn/`. Contains ZhihuExtractor with DynamicFetcher (Playwright). Discovered via `entry_points` group `clawithme.extractors`.

### Engines (9 total)

| Engine | Classifier | Sites | Source |
|--------|-----------|:-----:|--------|
| `base_http_status` | status_code | — | Original |
| `base_http_message` | message | — | Original |
| `base_http_headers` | headers | — | Original |
| `xenforo` | message | 222 migrated | Ported from maigret_china |
| `discourse` | message | 92 migrated | Ported from maigret_china |
| `wordpress_author` | status_code | 9 migrated | Ported from maigret_china |
| `phpbb` | message | 157 migrated | Ported from maigret_china |
| `vbulletin` | message | 120 migrated | Ported from maigret_china |
| **discuz** | message | — | **Original (not in maigret/maigret_china)** |

### Profile fields (16)

`site_id`, `site_name`, `url`, `username`, `display_name`, `bio`, `avatar_url`, `avatar_phash`, `email`, `phone`, `location`, `joined_date`, `post_count`, `follower_count`, `following_count`, `extra`

### Signal weights

| Signal | Weight | Logic | Threshold |
|--------|:------:|-------|:---------:|
| email | 1.0 | Exact, case-insensitive | — |
| phone | 0.95 | Digits-only, normalized | — |
| avatar_phash | 0.8 | Hamming distance | ≤10 |
| username | 0.7 | Levenshtein + affix/digit patterns | ≥0.80 |

## Phase Completion

| Phase | Name | Status |
|:-----:|------|:------:|
| 1 | Basic Verification | ✅ Code complete |
| 2 | Site DB Expansion | ✅ Code complete |
| 3 | Deep Crawler | ✅ **19 extractors (P0+P1 done)** |
| 4 | Multi-Signal Correlation | ✅ Jury-audited |
| 5 | Panorama Report | ✅ v2 features done |

### Audit rounds (5 completed)

1. ✅ Jury Round 1 — maigret dead code purge, empty stubs fix, HTTP unification
2. ✅ Jury Round 2 — stubs marked, migration artifacts deleted, test gaps filled
3. ✅ Code-Review-Excellence — Python quality + Security dual-perspective (29 findings, 8 fixed)
4. ✅ Functional QA — 7 false completions resolved, 3 bugs fixed
5. ✅ Claude Code Architecture — 5 code issues + 10 edge cases → 4-step dev plan

### Migration: maigret → clawithme

Commit `57be4e2`: Batch-migrated 3120 sites from maigret_china (MIT) to `data/sites/migrated/`.
- 2487 active, 632 disabled, 37 skipped
- 100% engine_ref coverage (auto-assigned: xenforo 222, phpbb 157, vbulletin 120, discourse 92, flarum 15, wordpress 9)
- Accessed via CLI: `clawithme search <user> --include-migrated`

### CI Verification Status

```
verify_site --all (curated): 29 healthy | 0 no-checks | 7 degraded | 12 deprecated
```

GitHub Actions workflows deployed and verified (2026-05-05):
- `.github/workflows/ci.yml` — PR: schema validate + stats on push to main (✅ always green)
- `.github/workflows/daily-verify.yml` — Daily 08:00 UTC: verify all sites (⚠️ expected non-zero on degraded sites — monitoring signal, not failure)

### SPA Limitation

5 sites fundamentally undetectable via HTTP: Twitter/X, Twitch, 少数派, SlideShare, 微博. Marked `dynamic_fetch: true` with known architecture limitation — no engine type can solve SPA shells returning identical HTML for exist/nonexist users.

## Test Results (2026-05-05)

### Unit
- **160 tests** all passing, Ruff 0, 2.06s

### End-to-end (liberborn)
- 13/36 hits, 3 profiles (dev.to/github/gitlab), 1 cluster (confidence 0.7)

### End-to-end (yes999zc)
- 10/36 hits, 3 profiles (github/zhihu/coolapk), 1 cluster (confidence 0.7)

## How to run

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
pip install -e ".[dev]"

# Search username (curated 36 sites)
clawithme search yes999zc --acknowledge-ethical-use

# Search email (auto-detected)
clawithme search yes999zc@163.com --acknowledge-ethical-use

# Search (all 2487 sites — SLOW)
clawithme search yes999zc --include-migrated --acknowledge-ethical-use

# Generate report
clawithme search yes999zc --report report.html --acknowledge-ethical-use
clawithme search yes999zc --report report.json --format json --acknowledge-ethical-use

# Tests & validation
python -m pytest tests/ -v          # 160 tests
python scripts/validate.py          # Schema validation
python scripts/stats.py             # Database statistics
python scripts/verify_site.py zhihu # Single site verification
python scripts/verify_site.py --all # Full verification
```

## Git Status (2026-05-06)

Local ↔ GitHub aligned. Phase 6 complete + V2 Phase 1 done. 209 tests.

| Phase | Status | Commits |
|:-----:|:------:|---------|
| 1-5 | ✅ | v1 baseline |
| 6 + V2 P1 | ✅ | 5 commits (e657aa1: B1-B4 + jury audit 🔴🟡 fixes) |
| 7 | ✅ | 7 commits, 30h (Batches 1-5 all done) |
| 8 | 🟡 | ~60h pending (Web UI + PDF + Tianyancha) |

**Phase 7 deliverables** (HEAD f50a13a):
- Anti-merge logic for username-only weak links
- Async pipeline (semaphore=10, 180s→~14s)
- Multi-provider LLM verifier (DeepSeek/Kimi/DashScope) with structured confidence scoring
- 9 international extractors: Reddit, HN, LinkedIn, Medium, YouTube, Telegram, Steam, Quora, ProductHunt
- 6 CN extractors: Douban, Juejin, Baidu Zhidao, NGA, Zcool, Netease Music
- 34 extractors total (was 19). 235 tests. Ruff 0.

**Phase 6 + V2 Phase 1 deliverables** (HEAD e657aa1):
- 7-signal rules engine with weighted Union-Find (avatar_phash=0.8, username=0.7, email=1.0, phone=0.95)
- LLM Verifier (DeepSeek Flash, provider-agnostic openai-compatible client)
- SQLite ResultCache with TTL (prerequisite for Web UI)
- Default avatar hash library (GitHub identicon + forum defaults)
- 4 deprecated CN sites revived: Gitee (API, email/weibo/QQ fields!), 掘金, AcFun, 网易云音乐
- Extractor health monitoring (weekly smoke tests, breakage detection)
- CI/CD auto release (GitHub Release → PyPI on tag push)
- 2 rounds jury audit, 🔴🟡 all fixed
- 209 tests (160 → 209), Ruff 0 (by policy)

## Key Design Decisions

| Decision | Rule |
|----------|------|
| Site storage | One JSON per site |
| Engine storage | Separate `engines.json` |
| Detection type | Engine `.classifier` only (not site `.check.type`) |
| HTTP layer | Scrapling Fetcher (curl_cffi fingerprinting) |
| Leak data | Pydantic BreachRecord, `password_sha256` only |
| Leak manager | Parallel multi-source, 15s timeout, graceful degradation |
| Template engine | Manual `str.replace` (no Jinja2), 7 variable whitelist |
| Logging | structlog + trace_id |
| Testing | Mock-based unit tests |
| Phone scope | International (7-15 digits, E.164 range) |
| Config | TOML, project-root `config.toml` (zero external deps) |
| CN code | Separate plugin repo (`clawithme-cn`), entry_points discovery |
| Extractor dispatch | `entry_points` group `clawithme.extractors`, `can_handle()` |
| Profile empty | `Profile.empty` is a property (bool), NOT a factory — return `Profile(site_id=..., ...)` for empty profiles |

## Quality Gates

1. **Ruff 0 (by policy)** — 2 intentional exceptions: `PLC0415` for lazy Fetcher import, `UP037` quoted type annotation
2. **Schema validation** — `python scripts/validate.py` before merge
3. **Site verification** — `python scripts/verify_site.py --all` daily
4. **209 tests passing** — `python -m pytest tests/ -v`

## Pending Work

| Item | Status |
|------|:------:|
| Local ↔ GitHub | ✅ aligned, no pending commits |
| Phase 6 (33h) | ✅ DONE (2026-05-06) |
| Phase 7 (88h) | 🟡 Pending |
| Phase 8 (60h) | 🟡 Pending |
| V2 total | ~181h across 3 phases

## V2 Direction (2026-05-05 四方评审 + 9哥决策)

**产品方向**：国际客户为主，中国站探测作为竞争优势。最终上线 SaaS。
**核心差异化**：LLM 身份推理引擎（规则 + DeepSeek Flash API 混合）。
**终局**：人脸识别 → 跨实名平台关联 → nuwa.world 式大图。

| # | Item | Status |
|:--:|------|:------:|
| 1 | 关联引擎：拆分误合并 cluster | 🟡 Phase 7 |
| 2 | 默认头像哈希库 | ✅ Phase 6 |
| 3 | 时间关联信号 | 🟡 Phase 7 |
| 4 | Extractor 健康监控 | ✅ Phase 6 |
| 5 | 修复误判 deprecated CN站 (Gitee/掘金/网易云/AcFun) | ✅ Phase 6 |
| 6 | CI/CD 自动发布 | ✅ Phase 6 |
| 7 | LLM 身份推理 POC (DeepSeek Flash) | ✅ Phase 6 |
| 8 | 结果缓存层 | ✅ Phase 6 |
| 9 | 位置邻近信号 | 🟡 Phase 7 |
| 10 | CLI async 重构 | 🟡 Phase 7 |
| 11 | LLM 推理正式化 | 🟡 Phase 7 |
| 12 | 国际站扩展 (LinkedIn/Reddit/Medium 等 10+ 站) | 🟡 Phase 7 |
| 13 | CN 站扩展至 30 (国际精华 + 中国金矿) | 🟡 Phase 7 |
| 14 | Web UI | 🟡 Phase 8 |
| 15 | PDF/Markdown 报告 | 🟡 Phase 8 |
| 16 | 天眼查 API (条件触发，需先拿实名) | 🟡 Phase 8 |
| — | 自建泄露库 | ❌ KILLED |
| — | 微信弱信号实验 | ❌ KILLED |
| — | Profile 提取 P1 | ✅ DONE (v1) |
| — | Louvain 图聚类 | ⏸️ v3 |

> Phase 1-7 全部完成。V2 Phase 1-7 DONE。34 extractors。235 tests。Async + LLM 正式化。CI + auto release。
