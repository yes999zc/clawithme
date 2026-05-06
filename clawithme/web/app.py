"""clawithme Web UI — FastAPI + SSE streaming search.

Usage::

    python -m clawithme.web.app
    # → http://localhost:8000
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
import signal
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from clawithme.cache import ResultCache
from clawithme.cli import load_all_sites
from clawithme.config import load_config
from clawithme.crawler.registry import discover_extractors
from clawithme.engine.loader import load_engines
from clawithme.logging import get_logger, new_trace_id
from clawithme.pipeline import AsyncPipeline
from clawithme.signals.llm_verifier import LLMVerifier

logger = get_logger()

app = FastAPI(title="clawithme", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter


@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src * data:; connect-src 'self'"
    )
    return response


@app.on_event("startup")
async def _preload_state():
    """Preload expensive resources at startup so requests don't pay the cost."""
    app.state.config = load_config()
    app.state.sites = load_all_sites(include_migrated=False)
    app.state.engines = load_engines()
    app.state.extractors = discover_extractors()
    app.state.cache = ResultCache()

# ── Static frontend ────────────────────────────────────────────

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    html = (_STATIC_DIR / "index.html").read_text()
    return HTMLResponse(html)


# ── SSE Search ─────────────────────────────────────────────────


async def _search_stream(username: str, request: Request):  # noqa: PLR0911, PLR0912, PLR0915
    """SSE generator: yields events as the pipeline progresses."""
    trace_id = new_trace_id()
    log = get_logger(trace_id=trace_id, username=username)
    cfg = load_config()

    t0 = time.monotonic()

    # Phase 0: Setup
    yield _sse("phase", json.dumps({"phase": "setup", "message": "Loading..."}))
    if await request.is_disconnected():
        log.info("client_disconnected", phase="setup")
        return

    try:
        sites = request.app.state.sites
    except AttributeError:
        try:
            sites = load_all_sites(include_migrated=False)
        except (OSError, json.JSONDecodeError):
            yield _sse("error", "Failed to load site data")
            return
        engines = load_engines()
        extractors = discover_extractors()
        cache = ResultCache()
    else:
        engines = request.app.state.engines
        extractors = request.app.state.extractors
        cache = request.app.state.cache
    llm = LLMVerifier()
    llm_verifier = llm if llm.is_configured() else None

    yield _sse("phase", json.dumps({
        "phase": "probe",
        "message": f"Probing {len(sites)} sites...",
        "total": len(sites),
    }))
    if await request.is_disconnected():
        log.info("client_disconnected", phase="probe")
        return

    pipeline = AsyncPipeline(
        sites, engines, extractors, cfg,
        cache=cache, llm_verifier=llm_verifier,
    )

    try:
        try:
            result = await asyncio.wait_for(pipeline.run(username), timeout=120)
        except TimeoutError:
            log.error("pipeline_timeout", timeout_s=120)
            yield _sse("error", "Pipeline timed out after 120s")
            return
        except (OSError, ValueError, RuntimeError) as e:
            log.error("pipeline_failed", error=str(e))
            msg = "Pipeline failed: I/O error" if isinstance(e, OSError) else str(e)
            yield _sse("error", msg)
            return

        elapsed = round(time.monotonic() - t0, 1)

        # Stream hits
        for h in result.hits:
            if await request.is_disconnected():
                log.info("client_disconnected", phase="stream_hits")
                return
            yield _sse("hit", json.dumps({
                "site_id": h["site_id"],
                "site_name": h["site_name"],
                "url": h["url"],
            }))

        # Stream profiles
        for p in result.profiles:
            if await request.is_disconnected():
                log.info("client_disconnected", phase="stream_profiles")
                return
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
                if await request.is_disconnected():
                    log.info("client_disconnected", phase="stream_clusters")
                    return
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
    except Exception as e:
        log.error("search_stream_failed", error=str(e), type=type(e).__name__)
        yield _sse("error", f"Internal error: {type(e).__name__}")


@app.get("/api/search/{username}")
@limiter.limit("5/minute")
async def search_stream(username: str, request: Request):
    """SSE endpoint: streams search results as they arrive."""
    # Validate username
    if not username or not username.strip():
        return JSONResponse(status_code=400, content={"error": "Invalid username"})
    username = username.strip()
    if len(username) > 128:
        return JSONResponse(status_code=400, content={"error": "Invalid username"})
    if not re.match(r'^[a-zA-Z0-9._\-@+]+$', username):
        return JSONResponse(status_code=400, content={"error": "Invalid username"})

    # Ethics acknowledgment: header OR query param (EventSource can't set custom headers)
    ethics_header = request.headers.get("X-Ethics-Acknowledgement")
    ethics_param = request.query_params.get("ethics")
    if ethics_header != "true" and ethics_param != "true":
        return JSONResponse(status_code=400, content={"error": "Ethics acknowledgment required"})
    return StreamingResponse(
        _search_stream(username, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helpers ────────────────────────────────────────────────────


def _sse(event: str, data: str) -> str:
    """Format a Server-Sent Event."""
    return f"event: {event}\ndata: {data}\n\n"


# ── Entry point ────────────────────────────────────────────────


def main():
    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    async def shutdown():
        server.should_exit = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(ValueError, NotImplementedError):
            signal.signal(sig, lambda s, f: asyncio.create_task(shutdown()))

    server.run()


if __name__ == "__main__":
    main()
