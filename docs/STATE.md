# clawithme — Project State

> Handoff document for fresh session. Last updated: 2026-05-05 (Step 3 complete — known_accounts population)

## What is clawithme

OSINT tool. Input: username → Output: identity panorama across social platforms.
Repo: `github.com/yes999zc/clawithme` (MIT, public)

## Current Code State

```
~4700 lines Python, 42 .py files, 116 tests (main) + 7 (plugin) = 123 total
48 site JSONs (36 active, 12 deprecated), 6 engines, 2 extractors
Phase 1-5 COMPLETE + jury audit fixed + Step 1-3 hardening COMPLETE
Ruff 0
```

### Key files to know

| File | Purpose |
|------|---------|
| `clawithme/cli.py` | CLI entry: `clawithme search <username> [--report <path>] [--format json]` |
| `clawithme/config.py` | TOML config loader (proxy, engines, user-agent) |
| `clawithme/engine/http_client.py` | Scrapling Fetcher wrapper |
| `clawithme/engine/engines.py` | Engine runner + template sandbox |
| `clawithme/engine/loader.py` | Load engines.json, match sites to engines |
| `clawithme/leak_sources/__init__.py` | BreachRecord (Pydantic) + LeakSource ABC + CavalierSource |
| `clawithme/leak_sources/hibp.py` | HIBP v3 API integration (no-key graceful degradation) |
| `clawithme/leak_sources/manager.py` | LeakSourceManager — parallel Cavalier+HIBP, 15s timeout, dedup |
| `clawithme/logging.py` | structlog + trace_id |
| `clawithme/crawler/base.py` | Profile dataclass (17 fields) + ProfileExtractor ABC |
| `data/schema.json` | JSON Schema for site definitions |
| `data/taxonomy.json` | Valid classification values |
| `data/engines.json` | 6 engine definitions |
| `data/sites/*/<id>.json` | One JSON per site, per primary category |
| `scripts/validate.py` | Schema validation (48 OK) |
| `scripts/verify_site.py` | Test a site's detection rule (known_accounts + known_unclaimed) |
| `scripts/stats.py` | Site DB statistics |
| **Signals (Phase 4)** | |
| `clawithme/signals/avatar.py` | pHash compute + Hamming distance + AvatarMatch NamedTuple |
| `clawithme/signals/correlation.py` | Union-Find clustering engine + Cluster dataclass (with evidence) |
| `clawithme/signals/extraction.py` | Email/phone regex extraction + normalize_phone() + disposable filter |
| `clawithme/signals/username.py` | Levenshtein distance + compare_usernames() (affix/digit patterns) |
| **Report (Phase 5)** | |
| `clawithme/report/generator.py` | Geist HTML report + JSON export + 3-tier confidence + evidence traceability |

### How to run

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
pip install -e ".[dev]"
python -m clawithme.cli search yes999zc
python -m clawithme.cli search yes999zc --report report.html
python -m clawithme.cli search yes999zc --report report.json --format json
python -m pytest tests/ -v
python scripts/validate.py
python scripts/stats.py
python scripts/verify_site.py zhihu
python scripts/verify_site.py --all    # CI daily verification
```

### CI Verification Status

```
verify_site --all: 29 healthy | 0 no-checks | 7 degraded | 12 deprecated
```

All 36 active sites have `known_accounts` + `known_unclaimed` populated.
7 degraded sites are known SPA/anti-bot issues → Step 4 (DynamicFetcher).

### Signal correlation model

| Signal | Weight | Logic | Threshold |
|--------|:------:|-------|:---------:|
| email | 1.0 | Exact, case-insensitive | — |
| phone | 0.95 | Digits-only, normalized | — |
| avatar_phash | 0.8 | Hamming distance | ≤10 |
| username | 0.7 | Levenshtein + affix/digit patterns | ≥0.7 |

### Cluster confidence badge tiers

| Confidence | Badge | Color |
|:----------:|-------|-------|
| ≥90% | badge-high | Green |
| 70–89% | badge-mid | Orange |
| <70% | badge-low | Red |

## Phase Completion

### Phase 1 ✅ — Basic Verification
### Phase 2 ✅ — Site Database Expansion (48 sites, 6 engines, CI)
### Phase 3 ✅ — Deep Crawler (jury-audited)
### Phase 4 ✅ — Multi-Signal Correlation (jury-audited)
### Phase 5 ✅ — Panorama Report (jury-audited)

### Hardening Steps (post-audit 4-step plan)

**Step 1 ✅ — Config system + error hardening** (`82caa3a`)
- `clawithme/config.py` — TOML config (proxies, engines, user-agent), zero external deps
- `with_error_context` for JSON parse errors → user-friendly messages
- CLI `--format` validation, proxy status display

**Step 2 ✅ — HIBP + LeakSource manager** (`cfdc16a`)
- HIBP v3 API email breach query (k-anonymity, no key → graceful degradation)
- LeakSourceManager: Cavalier + HIBP parallel, 15s timeout, dedup, single-source failure isolation
- CLI output: `Leak records: N (sources: Cavalier, HIBP)`

**Step 3 ✅ — Site DB audit + CONTRIBUTING** (`af0a927`)
- verify_site.py: NO CHECKS status for sites without known_accounts (was silent pass)
- All 36 active sites populated with `known_accounts` + `known_unclaimed`
- CONTRIBUTING.md: known_accounts requirements + verification workflow
- Ruff 0 (fixed 6 pre-existing lint issues from Step 2)

**Step 4 ✅ — DynamicFetcher engine integration** (`0a4bba9`)
- Engine.probe() supports `check.dynamic_fetch` → Playwright DynamicFetcher
- verify_site.py: DynamicFetcher support + 🔒 AUTH-GATED status
- medium: status_code → message engine → HEALTHY
- hupu: marked auth-gated (profiles require login)
- sspai/twitch/twitter/spotify/slideshare: dynamic_fetch=true (infra complete)
- **Key finding**: DynamicFetcher does NOT solve SPA detection — shells return identical HTML for exist/nonexist users. Accepted as known architecture limitation.
- CI status: 30 healthy | 1 auth-gated | 5 SPA-degraded | 12 deprecated

## Key Design Decisions

| Decision | Rule |
|----------|------|
| Site storage | One JSON per site |
| Engine storage | Separate engines.json |
| Detection type | Engine.classifier only |
| HTTP layer | Scrapling Fetcher |
| Leak data | Pydantic BreachRecord, password_sha256 only |
| Leak manager | Parallel multi-source, 15s timeout, graceful degradation |
| Template engine | Manual str.replace (no Jinja2) |
| Logging | structlog + trace_id |
| Testing | Mock-based unit tests |
| Phone scope | China mobile only (1[3-9]XXXXXXXXX) |
| Config | TOML (`~/.config/clawithme/config.toml`), zero external deps |

## Quality Gates

1. **Phase cleanup commit mandatory**
2. **Content spot-check** — verify ≥3 random samples
3. **CI must run** — validate.py + verify_site --all + tests before phase completion
4. **Ruff 0** — enforced at every commit

## v2 Scope (deferred)

- Default avatar hash DB
- Ethical use gates (--include-breaches, --acknowledge-ethical-use)
- Weighted-edge graph clustering (Louvain)
- 2000+ global site migration
- PDF/Markdown report export
- Location proximity signal
- Temporal correlation (joined_date)
- Self-hosted breach database (PostgreSQL on NAS)
- WeChat weak signal experiment
