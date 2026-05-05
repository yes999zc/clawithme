# clawithme Async Pipeline — Design Document

> Phase 7 Batch 1, Item 2. 2026-05-06.
> Karpathy: Think Before Coding.

## Current State

`cli.py::search()` 是 God function（~380 行），串行执行：

```
Phase 1:  Site probing    —— for site in sites: engine.probe() × 40  → ~180s
Phase 1.5: SearXNG         —— for site in sites[:50]: HTTP GET      → ~5s
Phase 2:  Profile extract  —— for hit in hits: extractor.extract()  → ~5s
Phase 3:  Leak DB          —— asyncio.run(query_leaks())             → ~3s
Phase 4:  Correlation      —— CorrelationEngine.correlate()         → ~0.1s
Total: ~190s
```

**瓶颈**：Phase 1 每个 probe ~4-5s，40 站串行 = 180s。

## Target State

```
Phase 1:  asyncio.gather(probes × 40, semaphore=10)  → ~20s (10x)
Phase 1.5: asyncio.gather(SearXNG × N, semaphore=5)  → ~3s
Phase 2:  asyncio.gather(extractors × M, semaphore=5) → ~3s
Phase 3:  asyncio (already async, integrated)         → ~3s
Phase 4:  sync (unchanged, <0.1s)                     → ~0.1s
Total: ~30s cold / ~5s cached → **6-38x speedup**
```

## Architecture

### Pipeline Model: Sequenced Stages

Not a free-for-all worker pool. Each stage gates on the previous:

```
┌─────────────┐    ┌──────────────────┐    ┌─────────────┐
│  Cache       │───▶│  Probe (async)   │───▶│  Extract     │
│  (sync,fast) │    │  semaphore=10    │    │  semaphore=5 │
└─────────────┘    └──────────────────┘    └─────────────┘
                                                      │
┌─────────────┐    ┌──────────────────┐               │
│  Correlation │◀───│  Leak DB (async) │◀──────────────┘
│  (sync)      │    │  semaphore=2     │
└─────────────┘    └──────────────────┘
```

### Component: `AsyncPipeline`

New module: `clawithme/pipeline.py`

```python
class AsyncPipeline:
    def __init__(self, config, cache, llm_verifier):
        self._probe_sem = asyncio.Semaphore(10)
        self._extract_sem = asyncio.Semaphore(5)

    async def run(self, username: str) -> SearchResult:
        # 1. Probe sites (cache-aware, async)
        hits = await self._probe_sites(username)
        # 2. SearXNG fallback (async)
        searxng_hits = await self._searxng_fallback(username, hit_ids)
        # 3. Extract profiles (async)
        profiles = await self._extract_profiles(username, hits)
        # 4. Leak DB (async)
        leak_records = await self._query_leaks(username)
        # 5. Correlate (sync — <100ms, not worth async)
        clusters = engine.correlate(all_profiles)
        return SearchResult(hits, profiles, leak_records, clusters)

    async def _probe_sites(self, username: str) -> list[dict]:
        tasks = []
        for site in self.sites:
            cached = self.cache.get(f"probe:{username}:{site['id']}")
            if cached:
                if cached["exists"]:
                    self.hits.append(cached["hit"])
                continue  # cache hit — skip probe
            tasks.append(self._probe_one(site, username))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        ...

    async def _probe_one(self, site, username):
        async with self._probe_sem:
            engine = get_engine_for_site(site, self.engines)
            result = await asyncio.to_thread(engine.probe, site, username)
            ...
```

### Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Concurrency model | `asyncio.Semaphore` + `asyncio.gather` | Simple, proven. worker pool overkill |
| Probe concurrency | 10 | Most sites tolerate moderate concurrency |
| Extract concurrency | 5 | Extracts do heavier HTTP + parsing |
| `engine.probe()` | `asyncio.to_thread()` | Probe is sync Scrapling — run in thread pool |
| Cache layer | Sync, check before async gather | SQLite is thread-safe at read level; single writer |
| Error isolation | `return_exceptions=True` | One probe crash doesn't kill pipeline |
| Sync fallback | `--sync` flag | Debug tool; keep old serial path alive in v1 |
| Phase 1.5 (SearXNG) | Integrated into async gather | Reduce total async overhead |
| Report generation | Moved out of pipeline | Report writes file — side effect kept at CLI level |

### Sync Fallback

Keep the existing serial `search()` function untouched, renamed internally.
New entry point tries async first, falls back to sync on `--sync` flag or if event loop fails.

```python
def search(username, ..., async_mode=True):
    if async_mode:
        try:
            asyncio.run(_async_search(username, ...))
        except RuntimeError:
            # Nested event loop — fall back to sync
            _sync_search(username, ...)
    else:
        _sync_search(username, ...)
```

### Wiring

Integration points:
1. `cli.py` — replace `search()` body with `AsyncPipeline.run()` call
2. `cli.py` — rename old search to `_search_sync()` (keep for fallback)
3. `clawithme/pipeline.py` — new file, ~200 lines
4. `clawithme/cli.py` — add `--sync` flag to main()

### Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|:--:|:--:|------|
| Scrapling thread-safety | Med | High | `asyncio.to_thread` isolates; test with 10 concurrent |
| Rate limiting (429s) | Low | Med | Semaphore=10 keeps it moderate; extractors already have backoff |
| Cache race conditions | Low | Low | SQLite WAL mode; single writer in cache.set() |
| Event loop conflicts | Low | Med | Sync fallback path; detect nested loop |
| Memory pressure | Low | Low | Semaphore caps concurrent fetches |

### Test Strategy

1. `test_pipeline_async.py` — mock `engine.probe`, verify gather parallelism
2. `test_pipeline_cache.py` — cache hit skips probe, cache miss triggers probe
3. `test_pipeline_error_isolation.py` — one probe failure doesn't block others
4. `test_pipeline_sync_fallback.py` — `--sync` uses old serial path
5. Keep all existing tests passing (214 → ~225)

### Implementation Phases

| Batch | Item | Hours | Deliverable |
|:-----:|------|:----:|------|
| B1-P2 | Design doc + architecture review | 2h | This document |
| B2 | `pipeline.py` + `_probe_sites()` | 5h | Core async probing |
| B2 | `_extract_profiles()` async + SearXNG | 4h | Full Phase 1-2 async |
| B2 | Sync fallback + `--sync` flag | 3h | Safety net |
| B2 | Tests + E2E verification | 3h | 225 tests |

Total: 17h (for async refactor portion of Phase 7)
