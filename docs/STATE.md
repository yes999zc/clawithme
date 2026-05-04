# clawithme — Project State

> Handoff document for fresh session. Last updated: 2026-05-05

## What is clawithme

OSINT tool. Input: username → Output: identity panorama across social platforms.
Repo: `github.com/yes999zc/clawithme` (MIT, public)

## Current Code State (audit round 2 cleared)

```
1360 lines Python, 21 .py files, 20 tests (all passing)
48 site JSONs (37 active, 11 deprecated), all validate green
6 engines, 3 classifiers (status_code/message/headers)
```

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

## Next: Phase 3 — Deep Crawler

**Goal**: Crawl public info from discovered profiles (avatar hash, bio, posts).
**Dependency**: Phase 2 ✅, Audit Round 1 ✅, Audit Round 2 ✅

### Tasks (from docs/todo.md)

1. **3.1.1** Generic crawler framework (`crawler/base.py`)
2. **3.1.2** Site-specific extractors (zhihu.py, github.py, etc.)
3. **3.1.3** Scrapling DynamicFetcher integration (Playwright Chromium for JS pages)
4. **3.2.1** Rate limiting + backoff
5. **3.2.2** User-Agent rotation
6. **3.3.1** Unified Profile dataclass

### Key architectural decisions for Phase 3

- **CRITICAL**: Before writing first extractor, create `clawithme-cn` plugin repo for China site code isolation
- DynamicFetcher needed for: B站, 微博, 虎扑, NGA, 少数派, 百度知道, 开源中国, 思否, 站酷
- Phase 2 established pattern: one extractor per site, same file-per-site approach as JSONs
- Empty packages waiting: `crawler/`, `signals/`, `report/`

## Phase 4-5 (future)

- Phase 4: Multi-signal association (email/phone/avatar hash linking)
- Phase 5: Panorama report (Geist web UI + export)

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

- Architecture isolation (China site plugin) — must happen before Phase 3 extractors
- WeChat weak signal experiment — not started
- Chat slang fingerprint library — v2
- Monitoring liveness probe — Phase 2.3.3 listed but not deployed
- Phase 3/4/5 packages: crawler/, signals/, report/ — stubs marked, implementation pending
