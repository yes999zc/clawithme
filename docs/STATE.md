# clawithme — Project State

> Handoff document for fresh session. Last updated: 2026-05-04 (post-round-2-audit)

## What is clawithme

OSINT tool. Input: username → Output: identity panorama across social platforms.
Repo: `github.com/yes999zc/clawithme` (MIT, public)

## Current Code State (architecture isolation ✅)

```\n~2800 lines Python, 32 .py files, 60 tests (all passing) + 7 zhihu tests (clawithme-cn)\n48 site JSONs (37 active, 11 deprecated), all validate green\n6 engines, 3 classifiers (status_code/message/headers)\n2 extractors: GithubExtractor (7 tests), ZhihuExtractor (7 tests), both output avatar_phash\nPhase 4.1: perceptual hashing (imagehash + Pillow), E2E verified\nRate limiting: 200ms global min delay, exponential backoff, 429/503 retry\nUA rotation: 6-browser pool, wired into static + dynamic fetchers\nDynamicFetcher: headless control, page_setup anti-webdriver, proxy passthrough\nCrawlerClient: proxy support, robots.txt compliance, context manager\nRuff: 0 errors\n```

### Key files to know

| File | Purpose |
|------|---------|
| `clawithme/cli.py` | CLI entry: `clawithme search <username>` |
| `clawithme/engine/http_client.py` | Scrapling Fetcher wrapper |
| `clawithme/engine/engines.py` | Engine runner + template sandbox |
| `clawithme/engine/loader.py` | Load engines.json, match sites to engines |
| `clawithme/leak_sources/__init__.py` | BreachRecord (Pydantic) + LeakSource ABC + CavalierSource |
| `clawithme/logging.py` | structlog + trace_id |
| `data/schema.json` | JSON Schema for site definitions |
| `data/taxonomy.json` | Valid classification values |
| `data/engines.json` | 6 engine definitions |
| `data/sites/*/<id>.json` | One JSON per site, per primary category |
| `scripts/validate.py` | Schema validation (48 OK) |
| `scripts/verify_site.py` | Test a site's detection rule |
| `scripts/stats.py` | Site DB statistics |
| `tests/test_http_client.py` | 5 tests (mock-based) |
| `tests/test_engines.py` | 8 tests (mock-based) |

### How to run

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
pip install -e ".[dev]"
python -m clawithme.cli search yes999zc
python -m pytest tests/ -v
python scripts/validate.py
python scripts/stats.py
python scripts/verify_site.py zhihu
```

### Classification system

- `identity_type`: real_social / public_social / virtual_social / anonymous / professional
- `geo_region`: cn / asia / europe / americas / global
- `primary`: social / devtools / forum / media / ecommerce / gaming / music / blog / academic

### Site database (48 total)

- 28 truly active (status_code discrimination works)
- 9 need DynamicFetcher for body analysis (probe_url filled, deprecated=false, Phase 3)
- 11 deprecated (403/timeout/captcha)

## Phase Completion

### Phase 1 ✅ — Basic Verification
Deliverable: CLI tool that probes 10 Chinese sites + queries Cavalier.
- Project skeleton + pyproject.toml + config
- Scrapling HTTP client wrapper
- JSON Schema + taxonomy
- 10 Chinese sites validated (7 active, 3 deprecated)
- Engine system (3 engines + sandbox + loader)
- LeakSource: BreachRecord Pydantic + ABC + CavalierSource
- CLI: `clawithme search <username>`
- Git commit chain: 41b4da6 → b254d24

### Phase 2 ✅ — Site Database Expansion
Deliverable: 48 sites + 6 engines + CI + docs.
- Expanded to 48 sites (37 active, 11 deprecated)
- maigret migration script
- 6 engines (status_code/message/headers/xenforo/discourse/wordpress)
- CI: PR checks + daily site verification
- CONTRIBUTING.md + stats + validate + healthcheck
- Legacy data.json cleaned up
- Git commit chain: 4039abd → 637f0d1

### Audit Cleanup ✅ — Post-Jury Fixes
- Removed 4500 lines of vendored maigret dead code (81% reduction)
- Fixed 7 shell sites with empty probe_url
- Fixed migration script .values() → .items() bug
- Unified HTTP layer (CavalierSource → HttpClient)
- Added 13 core tests (0 → 13)
- Fixed Claude-introduced bugs (missing BaseModel import, async bugs)
- Git commits: 2a95db1 → 3aaf4e5

### Audit Round 2 ✅ — Dependency & Stub Cleanup
- Removed unused httpx/aiohttp from dependencies (never imported)
- Deleted 7 unknown.json migration artifacts in data/sites/migrated/
- Marked 4 empty __init__.py stubs with TODO: Phase N markers
- Added smoke tests: test_loader.py (4) + test_cli.py (3) → 13→20 total
- All 20 tests pass, 48 sites validate green
- Git commit: 7fc4f57

### Architecture Isolation ✅ — Plugin System
- Created `clawithme-cn` plugin repo: github.com/yes999zc/clawithme-cn
- Main repo: `Profile` dataclass + `ProfileExtractor` ABC + `discover_extractors()` registry
- Plugin discovery via `importlib.metadata` entry_points group `clawithme.extractors`
- First extractor: `ZhihuExtractor` (skeleton, returns Profile)
- End-to-end verified: install `clawithme-cn` → `discover_extractors()` returns 1 extractor
- 10 new tests (crawler_base 8 + crawler_registry 2), 30 total all green
- Git commits: 2ea951d (main), 8105952 (clawithme-cn)

## Next: Phase 3 — Deep Crawler

**Goal**: Crawl public info from discovered profiles (avatar hash, bio, posts).
**Dependency**: Phase 2 ✅, Audit ✅, Architecture Isolation ✅

### Tasks (from docs/todo.md)

1. ✅ **3.1.1** Generic crawler framework (`crawler/base.py` + `client.py` + `registry.py`)
2. ✅ **3.1.2** Site-specific extractors — GithubExtractor (working), ZhihuExtractor (auth wall)
3. ✅ **3.1.3** Scrapling DynamicFetcher integration (via CrawlerClient, lazy init)
4. ✅ **3.3.1** Unified Profile dataclass
5. ✅ **3.2.1** Rate limiting + backoff (CrawlerClient: min_delay 200ms, exponential retry with 2 attempts)
6. ✅ **3.2.2** User-Agent rotation (6 Chrome/Firefox/Safari UAs, random_user_agent())

**Phase 3 — ALL 6/6 TASKS DONE ✅ (jury-audited + fixed)**

### Jury Audit (2026-05-04)

3 independent auditors found 21 issues (7 CRITICAL, 8 HIGH, 6 MEDIUM/LOW).
All 7 CRITICAL fixed in commit 86149bb.

**Round 2 fix** (commit 415fe03): All 11 remaining issues from Rounds 1+2 resolved:
- PII logging, 429/503 retry, proxy support, robots.txt, browser cleanup
- Registry collision detection, API exports, integration test, Zhihu tests
- DynamicFetcher stealth (page_setup callback removes navigator.webdriver)
- CrawlerClient context manager + close()

Tests: 57 (main) + 7 (plugin) = 64 total. Ruff: 0 errors.

### Key architectural decisions for Phase 3

- ~~**CRITICAL**: Before writing first extractor, create `clawithme-cn` plugin repo for China site code isolation~~ ✅ DONE
- Plugin system active: `discover_extractors()` finds 2 extractors (GithubExtractor + ZhihuExtractor)
- DynamicFetcher needed for: B站, 微博, 虎扑, NGA, 少数派, 百度知道, 开源中国, 思否, 站酷
- Phase 2 established pattern: one extractor per site, same file-per-site approach as JSONs
- Static Fetcher suitable for: GitHub, GitLab, StackOverflow, etc. (server-rendered HTML)

## Phase 4: Multi-Signal Association (in progress)

### 4.1 Avatar Perceptual Hashing ✅

- Renamed `avatar_hash` → `avatar_phash` (pHash, not SHA-256)
- `signals/avatar.py`: `compute_phash(image_bytes) → str | None`
- Both extractors download avatar → compute pHash
- E2E verified: Linus Torvalds → `c60c9933d19bcccd`; Karpathy → `8c857bd4b24bc999`
- Dependencies: imagehash>=4.3, Pillow>=10.0
- Tests: 3 (same/diff/invalid) + existing 60 = 63 total
- Git commit: 0e6ca02 (main), 62984e4 (clawithme-cn)

### 4.2 Avatar Cross-Platform Matching ✅

- `hamming_distance(phash1, phash2) → int` via XOR + `int.bit_count()`
- `compare_avatars(phash1, phash2, threshold=10) → {distance, is_match}`
- None-safe: either pHash is None → distance=-1, is_match=False
- Verified: Linus vs Karpathy distance=28 (>>threshold 10), same hash distance=0
- Tests: 8 avatar tests (3 compute + 2 hamming + 3 compare)
- Total: 65 (main) + 7 (plugin) = 72
- Git commit: 2f35ec6 (main)

### 4.3 Multi-Signal Correlation Engine ✅

- `CorrelationEngine.correlate(profiles) → list[Cluster]`
- Cluster: `{profiles, confidence, signals}` dataclass
- Union-Find algorithm with transitive closure across signals
- Signal weights: email=1.0, phone=0.95, avatar_phash=0.8
- Phone normalization: strips +86, spaces, dashes
- Profile extended with `email`/`phone` fields (None default)
- E2E: same avatar→cluster, transitive(phash+email)→1 cluster, different→separate
- Tests: 7 correlation + 65 existing = 72 (main) + 7 (plugin) = 79
- Git commit: 5b9ffe1 (main)

### 4.4 Email/Phone Signal Extraction ✅

- `signals/extraction.py`: `extract_emails(text)` / `extract_phones(text)` — pure regex
- Email: RFC 5322 simplified, deduplicated, lowercased
- Phone: Chinese mobile 1[3-9]XXXXXXXXX, strips +86/spaces/dashes
- GithubExtractor: extracts first email from profile bio
- Tests: 12 extraction + 72 existing = 84 (main) + 7 (plugin) = 91
- Git commit: d6e0523 (main)

### 4.5 CLI Integration — Pipeline All Signals (next)

## v2 Scope (deferred)

- Self-hosted breach database (PostgreSQL on NAS)
- 2000+ global site migration
- China site code isolation (clawithme-cn)

## Key Design Decisions

| Decision | Rule |
|----------|------|
| Site storage | One JSON per site |
| Engine storage | Separate engines.json |
| Detection type | Engine.classifier only, sites never declare type |
| Classification | 5 identity_types (incl. public_social) |
| HTTP layer | Scrapling Fetcher, not raw httpx |
| Leak data | Pydantic BreachRecord, password_sha256 only |
| Template engine | Manual str.replace (no Jinja2), variable whitelist |
| Logging | structlog + trace_id propagation |
| Testing | Mock-based unit tests for Engine + HttpClient |

## Quality Gates (learned from audit)

1. **Phase cleanup commit mandatory** — every phase must end with a cleanup/refactor commit
2. **Content spot-check** — "X items" claims must verify ≥3 random samples
3. **CI must run** — validate.py, tests must pass before phase completion

## Unresolved Items

- ~~Architecture isolation (China site plugin)~~ ✅ — clawithme-cn repo created, plugin system active
- WeChat weak signal experiment — not started
- Chat slang fingerprint library — v2
- Monitoring liveness probe — Phase 2.3.3 listed but not deployed
- Phase 3/4/5 packages: crawler/, signals/, report/ — stubs marked, implementation pending
