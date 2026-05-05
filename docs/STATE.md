# clawithme — Project State

> 手写于 2026-05-05（全代码审计后重写，替代旧 STATE.md）
> 源：真实代码库验证（47 .py files, 160 tests all passing, 9 engines, 3119 migrated sites）

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
| Deep extraction | None | GitHub + Zhihu extractors (CSS selector, Playwright) |
| Leak DB | None | Cavalier + HIBP with parallel manager |
| Correlation | None | Union-Find: email/phone/avatar_phash/username |
| Site scale | 3000+ (unverified) | 36 curated (verified) + 2523 migrated (engine-assigned) |

## Current Code State

```
~4650 lines Python, 47 .py files
160 tests (119 main + 41 leak sources), all passing, Ruff 0
48 site JSONs (36 active, 12 deprecated), 3119 migrated sites (2523 active)
9 engines, 2 extractors (GitHub + Zhihu in CN plugin)
Phase 1-5 code COMPLETE. CI deployment + v2 scope deferred.
```

### Key source files

| File | Lines | Purpose |
|------|:-----:|---------|
| `clawithme/cli.py` | 383 | CLI: `search`, `verify`, `validate`. Includes SearXNG fallback. |
| `clawithme/config.py` | 109 | TOML config loader (project-root `config.toml`, not `~/.config`) |
| `clawithme/engine/http_client.py` | — | Scrapling Fetcher wrapper |
| `clawithme/engine/engines.py` | — | Engine runner + template sandbox (`str.replace`, no Jinja2) |
| `clawithme/engine/loader.py` | — | Load engines.json, match sites to engines |
| `clawithme/leak_sources/__init__.py` | 235 | BreachRecord (Pydantic, 7 fields, field validators) + LeakSource ABC + CavalierSource |
| `clawithme/leak_sources/hibp.py` | 128 | HIBP v3 API (k-anonymity, no-key graceful degradation) |
| `clawithme/leak_sources/manager.py` | 91 | LeakSourceManager: parallel Cavalier+HIBP, 15s timeout, dedup |
| `clawithme/logging.py` | — | structlog + trace_id propagation |
| `clawithme/crawler/base.py` | 72 | Profile dataclass (16 fields) + ProfileExtractor ABC |
| `clawithme/crawler/client.py` | 300 | CrawlerClient: rate limiting, UA rotation, static+dynamic fetch |
| `clawithme/crawler/registry.py` | — | Plugin discovery via `importlib.metadata` entry_points |
| `clawithme/crawler/utils.py` | — | Shared extractor utilities: `first_text()`, `parse_count()` |
| `clawithme/crawler/extractors/github.py` | 96 | GitHubExtractor: static CSS-selected profile extraction + avatar phash |
| `clawithme/signals/avatar.py` | — | pHash compute + Hamming distance + AvatarMatch NamedTuple |
| `clawithme/signals/correlation.py` | 169 | Union-Find correlation engine, 4-signal weighted matching |
| `clawithme/signals/extraction.py` | — | International phone regex (7-15 digits, E.164), email extraction, disposable filter |
| `clawithme/signals/username.py` | — | Levenshtein distance + compare_usernames (affix/digit patterns) |
| `clawithme/report/generator.py` | 492 | Geist HTML report + JSON export, CSS-only charts, PII redaction |
| `clawithme/sites/__init__.py` | — | CN platform extension marker |
| `data/engines.json` | 159 | 9 engine definitions |
| `data/schema.json` | — | JSON Schema for site validation |
| `data/taxonomy.json` | — | Valid classification values |
| `data/sites/*/<id>.json` | — | 48 curated site JSONs (categories: social/devtools/forum/media/blog/gaming/music/ecommerce) |
| `data/sites/migrated/` | — | 3119 migrated sites (2523 active, engine auto-assigned) |
| `scripts/validate.py` | — | Schema validation (48 OK) |
| `scripts/verify_site.py` | — | Per-site detection rule verification (known_accounts + known_unclaimed) |
| `scripts/stats.py` | — | Site DB statistics |
| `scripts/healthcheck.py` | — | Core component liveness probe |
| `scripts/migrate_maigret.py` | — | maigret format → clawithme schema batch migration |

### Plugin: clawithme-cn

Separate repo at `~/AI_Workspace/01_Code/tools/clawithme-cn/`. Contains ZhihuExtractor with DynamicFetcher (Playwright) support. Discovered via `entry_points` group `clawithme.extractors`.

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
| 3 | Deep Crawler | ✅ Jury-audited |
| 4 | Multi-Signal Correlation | ✅ Jury-audited |
| 5 | Panorama Report | ✅ v2 features done |

### Hardening (4-step plan, all done)

| Step | Description | Commit |
|:----:|-------------|--------|
| 1 | Config system + error hardening | `82caa3a` |
| 2 | HIBP + LeakSource manager | `cfdc16a` |
| 3 | Site DB audit + CONTRIBUTING.md | `af0a927` |
| 4 | DynamicFetcher engine integration | `0a4bba9` |

### Audit rounds (5 completed)

1. ✅ Jury Round 1 — maigret dead code purge, empty stubs fix, HTTP unification
2. ✅ Jury Round 2 — stubs marked, migration artifacts deleted, test gaps filled
3. ✅ Code-Review-Excellence — Python quality + Security dual-perspective (29 findings, 8 fixed)
4. ✅ Functional QA — 7 false completions resolved, 3 bugs fixed
5. ✅ Claude Code Architecture — 5 code issues + 10 edge cases → 4-step dev plan

### Migration: maigret → clawithme

Commit `57be4e2`: Batch-migrated 3120 sites from maigret_china (MIT) to `data/sites/migrated/`.
- 2523 active, 632 disabled, 37 skipped
- 100% engine_ref coverage (auto-assigned: xenforo 222, phpbb 157, vbulletin 120, discourse 92, flarum 15, wordpress 9)
- Accessed via CLI: `clawithme search <user> --include-migrated`

### CI Verification Status

```
verify_site --all (curated): 29 healthy | 0 no-checks | 7 degraded | 12 deprecated
```

GitHub Actions workflows deployed and running:
- `.github/workflows/ci.yml` — PR: schema validate + stats on push to main
- `.github/workflows/daily-verify.yml` — Daily 08:00 UTC: verify all sites, manual trigger available

### SPA Limitation

5 sites fundamentally undetectable via HTTP: Twitter/X, Twitch, 少数派, SlideShare, 微博. Marked `dynamic_fetch: true` with known architecture limitation — no engine type can solve SPA shells returning identical HTML for exist/nonexist users.

## How to run

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
pip install -e ".[dev]"

# Search (curated 36 sites)
python -m clawithme.cli search yes999zc --acknowledge-ethical-use

# Search (all 2523 sites)
python -m clawithme.cli search yes999zc --include-migrated --acknowledge-ethical-use

# Generate report
python -m clawithme.cli search yes999zc --report report.html --acknowledge-ethical-use
python -m clawithme.cli search yes999zc --report report.json --format json --acknowledge-ethical-use

# Tests & validation
python -m pytest tests/ -v          # 160 tests
python scripts/validate.py          # Schema validation
python scripts/stats.py             # Database statistics
python scripts/verify_site.py zhihu # Single site verification
python scripts/verify_site.py --all # Full verification
```

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

## Quality Gates

1. **Ruff 0** — enforced at every commit
2. **Schema validation** — `python scripts/validate.py` before merge
3. **Site verification** — `python scripts/verify_site.py --all` daily
4. **160 tests passing** — `python -m pytest tests/ -v`

## Pending Work

| Item | Status |
|------|:------:|
| v2 scope (10 items, see docs/todo.md) | 🟡 Deferred |

> Phase 1-5 全部完成。CI 已部署（ci.yml + daily-verify.yml）。零待办。

## v2 Scope (deferred)

- 微信弱信号实验
- GitHub Actions CI/CD deployment
- Web UI (search interaction)
- 中国站扩展至 50+
- Default avatar hash DB
- Weighted-edge graph clustering (Louvain)
- PDF/Markdown report export
- Location proximity signal
- Temporal correlation (joined_date)
- Self-hosted breach database (PostgreSQL on NAS)
