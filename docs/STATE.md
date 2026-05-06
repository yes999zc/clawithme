# clawithme — Project State

> 2026-05-06 更新（Phase 9 全部完成，49 extractors，Ruff 真实 0 by policy）
> 源：代码统计验证（243 tests passing, 9 engines, 49 extractors, 49 curated sites + 3119 migrated）

## What is clawithme

OSINT tool: username → identity panorama across platforms.
Repo: `github.com/yes999zc/clawithme` (MIT, public)
Reference projects: [maigret](https://github.com/soxoj/maigret) (25k★) + [maigret_china](https://github.com/zuo-qirun/maigret_china) — CMS engine detection logic ported; architecture is ground-up redesign.

| vs maigret/maigret_china | They | clawithme |
|---|---|---|
| Site storage | Monolithic `data.json` | One JSON per site + JSON Schema validation |
| Detection | Single `checking.py` (~1200 lines, hardcoded) | 9 pluggable Engines in `engines.json` |
| HTTP layer | aiohttp + requests | Scrapling (anti-bot fingerprinting) |
| Quality gate | None | CI: daily verify + Schema validation + Ruff 0 (by policy) |
| Deep extraction | None | **49 extractors** across P0/P1/P2 |
| Leak DB | None | Cavalier + HIBP with parallel manager |
| Correlation | None | Union-Find: email/phone/avatar_phash/username |
| Site scale | 3000+ (unverified) | 44 curated (verified) + 2487 migrated (engine-assigned) |
| CLI search | username only | username + email + phone (auto-detect) |

## Current Code State

```
~5700 lines Python, 81 .py files + tests + scripts
243 tests passing, 5 skipped, Ruff 0 by policy (6 exceptions: 4 PLC0415 + 2 E501)
49 curated site JSONs (44 active, 5 deprecated), 3119 migrated sites (2487 active)
9 engines, 49 extractors
Phase 1-9 COMPLETE. Web UI + PDF + multi-format reports + confidence scoring DONE.
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
| `clawithme/pipeline.py` | 380 | Async pipeline orchestrator: semaphore-bounded parallel probes + extraction |
| `clawithme/crawler/extractors/` | 49 files | See extractor table below |
| `clawithme/signals/avatar.py` | — | pHash + Hamming distance + AvatarMatch |
| `clawithme/signals/correlation.py` | 169 | Union-Find, 4-signal weighted matching |
| `clawithme/signals/extraction.py` | — | Phone regex (E.164) + email extraction + disposable filter |
| `clawithme/signals/username.py` | — | Levenshtein + compare_usernames (affix/digit patterns) |
| `clawithme/signals/llm_verifier.py` | 186 | LLM-based cluster verification (provider-agnostic, OpenAI-compatible API) |
| `clawithme/cache.py` | 92 | SQLite ResultCache with TTL, async-safe |
| `clawithme/report/generator.py` | **1369** | **Geist HTML + JSON export, CSS-only charts, PII redaction, i18n (zh/en)** |
| `data/default_avatars.json` | 5 | Default avatar pHash library (GitHub identicon, forum defaults) |
| `scripts/extractor_health.py` | 132 | Weekly extractor smoke tests, breakage detection |

**Report i18n**: `_STRINGS` dict with 60+ zh/en keys, `lang` parameter on `generate_report()`, all render functions localized. Default `lang="zh"`.

### Extractors (49 total)

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

**P2 (31 extractors) — Phase 7-9 expansion:**

| Extractor | Method | Site |
|-----------|--------|------|
| BaiduZhidaoExtractor | CSS | zhidao.baidu.com |
| BloggerExtractor | og:meta | blogger.com |
| ChessExtractor | API | chess.com |
| CodepenExtractor | og:meta | codepen.io |
| DiscogsExtractor | API | discogs.com |
| DoubanExtractor | CSS | douban.com |
| GiteeExtractor | API | gitee.com |
| GoodreadsExtractor | og:meta | goodreads.com |
| HackernewsExtractor | CSS | news.ycombinator.com |
| HupuExtractor | CSS | hupu.com |
| InstagramExtractor | og:meta | instagram.com |
| JuejinExtractor | CSS | juejin.cn |
| LeetcodeExtractor | og:meta | leetcode.com |
| LinkedinExtractor | CSS | linkedin.com |
| MediumExtractor | CSS | medium.com |
| NeteaseMusicExtractor | CSS | music.163.com |
| NgaExtractor | CSS | nga.cn |
| ProducthuntExtractor | CSS | producthunt.com |
| QuoraExtractor | CSS | quora.com |
| RedditExtractor | CSS | reddit.com |
| SlideshareExtractor | regex | slideshare.net |
| SspaiExtractor | Playwright | sspai.com |
| SteamExtractor | CSS | steamcommunity.com |
| TelegramExtractor | CSS | t.me |
| TiebaExtractor | CSS | tieba.baidu.com |
| TwitchExtractor | og:meta | twitch.tv |
| TwitterExtractor | Playwright | twitter.com |
| WeiboExtractor | regex | weibo.com |
| WordpressExtractor | og:meta | wordpress.com |
| YoutubeExtractor | Playwright | youtube.com |
| ZcoolExtractor | CSS | zcool.com.cn |

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
| 3 | Deep Crawler | ✅ 19 extractors (P0+P1 done) |
| 4 | Multi-Signal Correlation | ✅ Jury-audited |
| 5 | Panorama Report | ✅ v2 features done |
| 6 | Correlation Engine + Infra | ✅ LLM POC + CI/CD + health monitoring |
| 7 | Engine Upgrade + Site Expansion | ✅ Async pipeline + 15 extractors |
| 8 | Web UI + PDF + i18n | ✅ FastAPI + Geist + WeasyPrint |
| 9 | Confidence + Wrong-Person + Extractor Expansion | ✅ 16 new extractors + scoring system |

### Audit rounds (8 completed)

1. ✅ Jury Round 1 — maigret dead code purge, empty stubs fix, HTTP unification
2. ✅ Jury Round 2 — stubs marked, migration artifacts deleted, test gaps filled
3. ✅ Code-Review-Excellence — Python quality + Security dual-perspective (29 findings, 8 fixed)
4. ✅ Functional QA — 7 false completions resolved, 3 bugs fixed
5. ✅ Claude Code Architecture — 5 code issues + 10 edge cases → 4-step dev plan
6. ✅ 四方 V2 路线评审 — V2 re-prioritization, KILL #1/#6, LLM POC added
7. ✅ Phase 8 定点审计 — 6 issues (3🔴+3🟡), 13 new tests
8. ✅ Phase 8 陪审团全量审计 — 28 findings → 17 fixed (3 agents cross-ref)

### Migration: maigret → clawithme

Commit `57be4e2`: Batch-migrated 3120 sites from maigret_china (MIT) to `data/sites/migrated/`.
- 2487 active, 632 disabled, 37 skipped
- 100% engine_ref coverage (auto-assigned: xenforo 222, phpbb 157, vbulletin 120, discourse 92, flarum 15, wordpress 9)
- Accessed via CLI: `clawithme search <user> --include-migrated`

### CI Verification Status

```
verify_site --all (curated): 29 healthy | 0 no-checks | 7 degraded | 12 deprecated
```

GitHub Actions workflows deployed:
- `.github/workflows/ci.yml` — PR: schema validate + stats on push to main
- `.github/workflows/daily-verify.yml` — Daily 08:00 UTC: verify all sites
- `.github/workflows/release.yml` — GitHub Release → PyPI on tag push

### Phase 9: Confidence Scoring (核心变更)

**Confidence system** replaces old 3-tier classification:
- `_compute_hit_confidence()` — continuous 0.0–1.0 score (HTTP status + SPA + extractor data + display_name + field completeness)
- `_is_wrong_person()` — Levenshtein similarity + CJK script detection (avoids mislabeling Chinese names)
- `_username_similarity()` — helper for cross-site comparison
- Report: new "确认"/"待验证" badges + wrong-person ⚠ warnings + identity assessment card

### SPA Limitation

5 sites fundamentally undetectable via HTTP: Twitter/X, Twitch, 少数派, SlideShare, 微博. Marked `dynamic_fetch: true` with known architecture limitation. Phase 9 added Playwright-based extractors for all 5.

## Quality Gates

1. **Ruff 0 (by policy)** — 6 pre-existing exceptions: `PLC0415` lazy imports (scrapling Fetcher, bilibili, avatar) and `E501` line length (keybase, twitter)
2. **Schema validation** — `python scripts/validate.py` before merge
3. **Site verification** — `python scripts/verify_site.py --all` daily
4. **243 tests passing** — `python -m pytest tests/ -v`

## Git Status (2026-05-06)

Local ↔ GitHub aligned. Phase 1-9 all complete.

| Phase | Status | Commits |
|:-----:|:------:|---------|
| 1-5 | ✅ | v1 baseline |
| 6 | ✅ | 5 commits (B1-B4 + jury audit 🔴🟡 fixes) |
| 7 | ✅ | 7 commits, 30h (Batches 1-5 all done) |
| 8 | ✅ | 5 commits (Web UI + PDF + i18n + 2 audit rounds) |
| 9 | ✅ | 5 commits (confidence + P0 SPA + P1 + P2 + YouTube fix) |

## How to run

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
pip install -e ".[dev]"

# Search username (curated 44 sites)
clawithme search yes999zc --acknowledge-ethical-use

# Search email (auto-detected)
clawithme search yes999zc@163.com --acknowledge-ethical-use

# Search (all 2487 sites — SLOW)
clawithme search yes999zc --include-migrated --acknowledge-ethical-use

# Generate report
clawithme search yes999zc --report report.html --acknowledge-ethical-use
clawithme search yes999zc --report report.json --format json --acknowledge-ethical-use

# Tests & validation
python -m pytest tests/ -v          # 243 tests
python scripts/validate.py          # Schema validation
python scripts/stats.py             # Database statistics
python scripts/verify_site.py zhihu # Single site verification
python scripts/verify_site.py --all # Full verification
```

## V2 Direction (2026-05-05 四方评审 + 9哥决策)

**产品方向**：国际客户为主，中国站探测作为竞争优势。最终上线 SaaS。
**核心差异化**：LLM 身份推理引擎（规则 + DeepSeek Flash API 混合）。
**终局**：人脸识别 → 跨实名平台关联 → nuwa.world 式大图。

| # | Item | Status |
|:--:|------|:------:|
| 1 | 关联引擎：拆分误合并 cluster | ✅ Phase 6 |
| 2 | 默认头像哈希库 | ✅ Phase 6 |
| 3 | 时间关联信号 | ✅ Phase 6 |
| 4 | Extractor 健康监控 | ✅ Phase 6 |
| 5 | 修复误判 deprecated CN站 (Gitee/掘金/网易云/AcFun) | ✅ Phase 6 |
| 6 | CI/CD 自动发布 | ✅ Phase 6 |
| 7 | LLM 身份推理 POC (DeepSeek Flash) | ✅ Phase 6 |
| 8 | 结果缓存层 | ✅ Phase 6 |
| 9 | 位置邻近信号 | ✅ Phase 6 |
| 10 | CLI async 重构 | ✅ Phase 7 |
| 11 | LLM 推理正式化 | ✅ Phase 7 |
| 12 | 国际站扩展 (LinkedIn/Reddit/Medium 等 10+ 站) | ✅ Phase 7 |
| 13 | CN 站扩展至 30 (国际精华 + 中国金矿) | ✅ Phase 7 |
| 14 | Web UI | ✅ Phase 8 |
| 15 | PDF/Markdown 报告 | ✅ Phase 8 |
| 16 | 天眼查 API | ❌ CANCELLED |
| — | 自建泄露库 | ❌ KILLED |
| — | 微信弱信号实验 | ❌ KILLED |
| — | Profile 提取 P1 | ✅ DONE (v1) |
| — | Louvain 图聚类 | ⏸️ v3 |

| Phase 10 | **🔜 更多 extractor + 跨人聚类增强 + 服务器部署** |

> Phase 1-9 全部完成。243 tests。49 extractors。Web UI + PDF + 置信度系统 + 8 轮审计 DONE。
> 技术路线文档见 `docs/technical-roadmap.md`（截至 Phase 8 的计划文档，Phase 9 的实际执行记录在 `TODO.md`）。

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
| Confidence | Continuous 0.0-1.0 score (not 3-tier), CJK-aware wrong-person detection |
