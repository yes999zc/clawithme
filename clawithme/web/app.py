"""clawithme Web UI — FastAPI + SSE streaming search.

Usage::

    python -m clawithme.web.app
    # → http://localhost:8000
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from clawithme.cache import ResultCache
from clawithme.config import load_config
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import load_engines
from clawithme.logging import get_logger, new_trace_id
from clawithme.pipeline import AsyncPipeline
from clawithme.signals.llm_verifier import LLMVerifier

from .cli_web import load_all_sites

logger = get_logger()

app = FastAPI(title="clawithme", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static frontend ────────────────────────────────────────────

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    html = (_STATIC_DIR / "index.html").read_text()
    return HTMLResponse(html)


# ── SSE Search ─────────────────────────────────────────────────


async def _search_stream(username: str):
    """SSE generator: yields events as the pipeline progresses."""
    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)
    cfg = load_config()

    t0 = time.monotonic()

    # Phase 0: Setup
    yield _sse("phase", json.dumps({"phase": "setup", "message": "Loading..."}))

    try:
        sites = load_all_sites(include_migrated=False)
    except (OSError, json.JSONDecodeError) as e:
        yield _sse("error", str(e))
        return
    engines = load_engines()
    extractors = discover_extractors()

    cache = ResultCache()
    llm = LLMVerifier()
    llm_verifier = llm if llm.is_configured() else None

    yield _sse("phase", json.dumps({
        "phase": "probe",
        "message": f"Probing {len(sites)} sites...",
        "total": len(sites),
    }))

    pipeline = AsyncPipeline(
        sites, engines, extractors, cfg,
        cache=cache, llm_verifier=llm_verifier,
    )

    try:
        result = await pipeline.run(username)
    except (OSError, ValueError, TimeoutError, RuntimeError) as e:
        log.error("pipeline_failed", error=str(e))
        yield _sse("error", str(e))
        return

    elapsed = round(time.monotonic() - t0, 1)

    # Stream hits
    for h in result.hits:
        yield _sse("hit", json.dumps({
            "site_id": h["site_id"],
            "site_name": h["site_name"],
            "url": h["url"],
        }))

    # Stream profiles
    for p in result.profiles:
        yield _sse("profile", json.dumps({
            "site_id": p["site_id"],
            "display_name": p.get("display_name"),
            "location": p.get("location"),
            "bio": p.get("bio", "")[:200] if p.get("bio") else None,
            "avatar_url": p.get("avatar_url"),
            "follower_count": p.get("follower_count"),
        }))

    # Stream clusters
    multi_clusters = [c for c in result.clusters if len(c.profiles) > 1]
    if multi_clusters:
        for c in multi_clusters:
            yield _sse("cluster", json.dumps({
                "sites": [p.site_id for p in c.profiles],
                "confidence": c.confidence,
                "signals": c.signals,
            }))

    # Done
    yield _sse("done", json.dumps({
        "trace_id": trace_id,
        "hits": len(result.hits),
        "profiles": len(result.profiles),
        "leaks": len(result.leak_records),
        "clusters": len(result.clusters),
        "searxng_hits": result.searxng_hits,
        "elapsed_s": elapsed,
    }))


@app.get("/api/search/{username}")
async def search_stream(username: str, request: Request):
    """SSE endpoint: streams search results as they arrive."""
    return StreamingResponse(
        _search_stream(username),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Report ─────────────────────────────────────────────────────


@app.get("/api/report/{trace_id}")
async def report(trace_id: str):
    """Return an HTML report for a completed search (from cache)."""
    # For now: placeholder. Full impl reads from file cache.
    return HTMLResponse(
        f"<p>Report for {trace_id}: not yet implemented.</p>"
    )


# ── Helpers ────────────────────────────────────────────────────


def _sse(event: str, data: str) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {data}\n\n"


# ── Entry point ────────────────────────────────────────────────


def main():
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
