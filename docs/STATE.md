# clawithme — Project State

> Handoff document for fresh session. Last updated: 2026-05-04 (P4+P5 jury audit complete)

## What is clawithme

OSINT tool. Input: username → Output: identity panorama across social platforms.
Repo: `github.com/yes999zc/clawithme` (MIT, public)

## Current Code State

```
~4500 lines Python, 42 .py files, 116 tests (main) + 7 (plugin) = 123 total
48 site JSONs, 6 engines, 2 extractors
Phase 1-5 COMPLETE + jury audit fixed
Ruff 0
```

### Key files to know

| File | Purpose |
|------|---------|
| `clawithme/cli.py` | CLI entry: `clawithme search <username> [--report <path>] [--format json]` |
| `clawithme/engine/http_client.py` | Scrapling Fetcher wrapper |
| `clawithme/engine/engines.py` | Engine runner + template sandbox |
| `clawithme/engine/loader.py` | Load engines.json, match sites to engines |
| `clawithme/leak_sources/__init__.py` | BreachRecord (Pydantic) + LeakSource ABC + CavalierSource |
| `clawithme/logging.py` | structlog + trace_id |
| `clawithme/crawler/base.py` | Profile dataclass (17 fields) + ProfileExtractor ABC |
| `data/schema.json` | JSON Schema for site definitions |
| `data/taxonomy.json` | Valid classification values |
| `data/engines.json` | 6 engine definitions |
| `data/sites/*/<id>.json` | One JSON per site, per primary category |
| `scripts/validate.py` | Schema validation (48 OK) |
| `scripts/verify_site.py` | Test a site's detection rule |
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
```

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

### Phase 1 ✅ — Basic Verification (15 tasks, 7 commits)
### Phase 2 ✅ — Site Database Expansion (48 sites, 6 engines, CI)
### Audit Cleanup ✅ — Post-Jury Fixes (Round 1 + Round 2)
### Architecture Isolation ✅ — Plugin System (clawithme-cn)
### Phase 3 ✅ — Deep Crawler (jury-audited)

### Phase 4: Multi-Signal Association ✅

**4.1–4.5 ALL COMPLETE** + post-jury hardening:

```
4.1 ✅ avatar phash        — compute_phash()
4.2 ✅ avatar matching     — hamming_distance(), AvatarMatch NamedTuple
4.3 ✅ correlation engine  — Union-Find, 4-signal clustering (email/phone/avatar/username)
4.4 ✅ extraction          — extract_emails(), extract_phones(), disposable filter
4.5 ✅ CLI pipeline        — full integration in 'clawithme search'
4.x ✅ username signal     — Levenshtein + affix/digit pattern detection
```

### Phase 5: Panorama Report ✅

- **HTML**: Geist/Vercel grayscale, responsive (mobile @480px), system-ui font
- **JSON**: `export_json()` + CLI `--format json`
- **Evidence**: Reports WHY profiles were clustered (e.g., "alice@gmail.com", "distance=3")
- **Confidence**: 3-tier badges (green/orange/red)
- **Error handling**: OSError guarded on report write

## P4+P5 Jury Audit (2026-05-04)

3 independent auditors (Brutal Pragmatist / OSINT Expert / Architect) found 22 issues.
Fixed in 3 rounds (commits ad1c122 + prior):

### Round 1 — Critical bugs (3 fixes)
- Profile.empty now includes email/phone fields
- _detected_signals reports actual signal contributions, not field presence
- Deduplicated phone normalization: shared normalize_phone() in extraction.py

### Round 2 — Type safety + new signals (6 fixes)
- compare_avatars returns AvatarMatch NamedTuple (was bare dict)
- JSON report export (export_json + CLI --format json)
- Username similarity signal (Levenshtein + affix patterns, weight 0.7)
- hamming_distance raises ValueError on unequal-length hex
- _render_sites uses .get() instead of bare dict access

### Round 3 — Report UX + traceability (5 fixes)
- Mobile CSS @media (max-width: 480px)
- Report write OSError handling
- Confidence badge 3-tier: green(≥90%) / orange(≥70%) / red(<70%)
- Cluster evidence traceability: shows WHY profiles were linked
- Disposable email domain filter (21 domains)

### Remaining (deferred — needs discussion)

| Severity | Finding | Rationale |
|:--------:|---------|-----------|
| CRITICAL | Default avatar pHash false clusters | Needs known-default-avatar hash DB |
| CRITICAL | No ethical consent/opt-out mechanism | Design decision for public release |
| CRITICAL | Breach DB integration ethics | Gate behind --include-breaches flag |
| HIGH | OR logic chain-fusion guard | Requires AND/weighted threshold redesign |
| HIGH | CLI God function refactor | Large refactor, v2 |
| HIGH | Confidence model (arithmetic mean flaw) | v2 — Bayesian fusion |

## Key Design Decisions

| Decision | Rule |
|----------|------|
| Site storage | One JSON per site |
| Engine storage | Separate engines.json |
| Detection type | Engine.classifier only |
| HTTP layer | Scrapling Fetcher |
| Leak data | Pydantic BreachRecord, password_sha256 only |
| Template engine | Manual str.replace (no Jinja2) |
| Logging | structlog + trace_id |
| Testing | Mock-based unit tests |
| Phone scope | China mobile only (1[3-9]XXXXXXXXX) |

## Quality Gates

1. **Phase cleanup commit mandatory**
2. **Content spot-check** — verify ≥3 random samples
3. **CI must run** — validate.py + tests before phase completion

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
