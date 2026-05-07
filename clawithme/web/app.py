"""clawithme Web UI — FastAPI + SSE streaming search.

Usage::

    python -m clawithme.web.app
    # → http://localhost:8000
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import sys
import time
from contextlib import asynccontextmanager, suppress
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
from clawithme.engine.proxy_manager import ProxyManager
from clawithme.logging import get_logger, new_trace_id
from clawithme.pipeline import AsyncPipeline
from clawithme.report.generator import _compute_hit_confidence, _is_wrong_person
from clawithme.signals.llm_verifier import LLMVerifier
from clawithme.web.routes.admin import router as admin_router
from clawithme.web.routes.report import router as report_router, store_result

logger = get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: preload resources. Shutdown: clean up connections."""
    # ── Startup ──
    app.state.config = load_config()
    app.state.sites = load_all_sites(include_migrated=False)
    app.state.engines = load_engines(proxy_manager=ProxyManager(app.state.config))
    app.state.extractors = discover_extractors()
    app.state.cache = ResultCache()
    # Print banner after startup succeeds
    print()
    print(_BANNER)
    print(f"  🚀  WebUI running at http://localhost:8000\n")

    yield

    # ── Shutdown ──
    # ── Shutdown ──
    if hasattr(app.state, "cache") and app.state.cache is not None:
        app.state.cache.close()
    logger.info("app_shutdown")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="clawithme", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register sub-routers
app.include_router(report_router)
app.include_router(admin_router)


@app.middleware("http")
async def add_csp_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src * data:; connect-src 'self'"
    )
    return response

# ── Static frontend ────────────────────────────────────────────

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/")
async def index():
    html = (_STATIC_DIR / "index.html").read_text()
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@app.get("/admin")
async def admin_panel():
    """Proxy & site management panel."""
    admin_html = _STATIC_DIR / "admin.html"
    if not admin_html.exists():
        return HTMLResponse(
            content="<h1>Admin panel not found</h1>", status_code=404
        )
    html = admin_html.read_text()
    return HTMLResponse(
        content=html,
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


# ── SSE Search ─────────────────────────────────────────────────


async def _search_stream(username: str, request: Request, incremental: bool = False):  # noqa: PLR0911, PLR0912, PLR0915
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
        engines = load_engines(proxy_manager=ProxyManager(cfg))
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
        incremental=incremental,
    )

    # Pre-pipeline status so the user knows something is happening
    yield _sse("phase", json.dumps({
        "phase": "scanning",
        "message": "Scanning sites and querying leak databases...",
    }))

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

        # Build profile_by_site for confidence scoring
        profile_by_site: dict[str, dict] = {}
        for p in result.profiles:
            sid = p.get("site_id")
            if sid:
                profile_by_site[sid] = p

        # Stream hits
        for h in result.hits:
            if await request.is_disconnected():
                log.info("client_disconnected", phase="stream_hits")
                return
            site_id = h["site_id"]
            conf = _compute_hit_confidence(h, profile_by_site, username)
            wp = _is_wrong_person(h, profile_by_site, username)
            yield _sse("hit", json.dumps({
                "site_id": site_id,
                "site_name": h["site_name"],
                "url": h["url"],
                "status": h.get("status"),
                "category": h.get("site_def", {}).get("classification", {}).get("primary", "other"),
                "confidence": round(conf, 2),
                "wrong_person": wp,
            }))

        # Stream profiles
        for p in result.profiles:
            if await request.is_disconnected():
                log.info("client_disconnected", phase="stream_profiles")
                return
            yield _sse("profile", json.dumps({
                "site_id": p["site_id"],
                "username": p.get("username"),
                "display_name": p.get("display_name"),
                "location": p.get("location"),
                "bio": p.get("bio", "")[:200] if p.get("bio") else None,
                "avatar_url": p.get("avatar_url"),
                "email": p.get("email"),
                "phone": p.get("phone"),
                "joined_date": p.get("joined_date"),
                "post_count": p.get("post_count"),
                "follower_count": p.get("follower_count"),
                "following_count": p.get("following_count"),
                "extra": p.get("extra"),
                "empty": p.get("empty", True),
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
                    "evidence": c.evidence,
                    "profile_count": len(c.profiles),
                }))

        # Sources used
        sources_used = ["Cavalier"]
        if cfg.apis.hibp_api_key:
            sources_used.append("HIBP")

        # Stream leak records
        # First emit a status event showing per-source counts
        leak_by_source: dict[str, int] = {}
        for r in result.leak_records:
            src = r.source or "unknown"
            leak_by_source[src] = leak_by_source.get(src, 0) + 1
        yield _sse("leakstatus", json.dumps({
            "total": len(result.leak_records),
            "per_source": leak_by_source,
            "sources_used": sources_used,
        }))
        for r in result.leak_records:
            if await request.is_disconnected():
                log.info("client_disconnected", phase="stream_leaks")
                return
            yield _sse("leak", json.dumps({
                "email": r.email,
                "username": r.username,
                "phone": r.phone,
                "domain": r.domain,
                "source": r.source,
                "breach_date": r.breach_date,
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
            "sources_used": sources_used,
            "llm_configured": llm_verifier is not None,
        }))

        # Store result for later report download
        req_lang = request.query_params.get("lang", "zh")
        store_result(trace_id, result, lang=req_lang if req_lang in ("zh", "en") else "zh")
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
    incremental = request.query_params.get("incremental", "false") == "true"
    return StreamingResponse(
        _search_stream(username, request, incremental=incremental),
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


_BANNER = r"""
                            ▄████████  ██▓    ▄▄▄       █     █░ ██▓▄▄▄█████▓ ██░ ██  ███▄ ▄███▓▓█████
                           ██▒    ██▒▓██▒   ▒████▄    ▓█░ █ ░█░▓██▒▓  ██▒ ▓▒▓██░ ██▒▓██▒▀█▀ ██▒▓█   ▀
                          ░██     ██▒▒██░   ▒██  ▀█▄  ▒█░ █ ░█ ▒██▒▒ ▓██░ ▒░▒██▀▀██░▓██    ▓██░▒███
                          ░██▓   ██▓▒▒██░   ░██▄▄▄▄██ ░█░ █ ░█ ░██░░ ▓██▓ ░ ░▓█ ░██ ▒██    ▒██ ▒▓█  ▄
                          ░▒██████▒▒ ░██████▒▓█   ▓██▒░░██▒██▓ ░██░  ▒██▒ ░ ░▓█▒░██▓▒██▒   ░██▒░▒████▒
                           ░ ▒░▓  ░  ░ ▒░▓  ░▒▒   ▓▒█░░ ▓░▒ ▒  ░▓    ▒ ░░    ▒ ░░▒░▒░ ▒░   ░  ░░░ ▒░ ░
                             ░ ░  ░  ░ ░ ▒  ░ ▒   ▒▒ ░  ▒ ░ ░   ▒ ░    ░     ▒ ░▒░ ░░  ░      ░ ░ ░  ░
                               ░       ░ ░    ░   ▒     ░   ░   ▒ ░  ░       ░  ░░ ░░      ░      ░
                               ░  ░      ░  ░     ░  ░    ░     ░            ░  ░  ░       ░      ░  ░

                                  🔍  Username → Identity Panorama  v0.1
                    📡 3,031 Sites · ⚡ 14s Cold Start · 🇨🇳 16 CN Platforms · 📋 4 Report Formats
"""


def main():
    """Start the WebUI server.

    On macOS with Homebrew, we automatically add /opt/homebrew/lib to
    DYLD_LIBRARY_PATH so WeasyPrint (PDF export) can find system libraries
    like libgobject-2.0.
    """
    import os
    import sys

    # macOS Homebrew library path fix for WeasyPrint
    if sys.platform == "darwin":
        brew_lib = "/opt/homebrew/lib"
        if os.path.isdir(brew_lib) and brew_lib not in os.environ.get("DYLD_LIBRARY_PATH", ""):
            current = os.environ.get("DYLD_LIBRARY_PATH", "")
            os.environ["DYLD_LIBRARY_PATH"] = f"{brew_lib}:{current}" if current else brew_lib

    config = uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info")
    server = uvicorn.Server(config)

    async def shutdown():
        server.should_exit = True

    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(ValueError, NotImplementedError):
            signal.signal(sig, lambda s, f: asyncio.create_task(shutdown()))

    server.run()


if __name__ == "__main__":
    main()
