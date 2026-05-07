"""Report download API — stores search results in-memory for export.

Usage:
    GET /api/report/{trace_id}?format=html|json|pdf&username=xxx
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response

from clawithme.report.generator import export_json, export_markdown, export_pdf, generate_report

if TYPE_CHECKING:
    from clawithme.pipeline import SearchResult

router = APIRouter(prefix="/api/report")

# In-memory result cache: trace_id → (SearchResult, expires_at, lang)
_report_cache: dict[str, tuple["SearchResult", float, str]] = {}
_REPORT_CACHE_TTL_S = 300  # 5 minutes


def store_result(trace_id: str, result: "SearchResult", lang: str = "zh") -> None:
    """Store a search result for later report download.

    Results expire after _REPORT_CACHE_TTL_S seconds.
    *lang* is stored alongside the result so downloads use the correct locale.
    """
    _report_cache[trace_id] = (result, time.time() + _REPORT_CACHE_TTL_S, lang)
    _evict_expired()


def _evict_expired() -> None:
    now = time.time()
    expired = [k for k, (_, et, _) in _report_cache.items() if et < now]
    for k in expired:
        del _report_cache[k]


def _get_result(trace_id: str) -> tuple["SearchResult", str]:
    """Get a stored result and its lang. Raises 404 if expired/missing."""
    entry = _report_cache.get(trace_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Report expired or not found")
    result, expires_at, lang = entry
    if time.time() > expires_at:
        del _report_cache[trace_id]
        raise HTTPException(status_code=404, detail="Report expired")
    return result, lang


@router.get("/{trace_id}")
async def download_report(
    trace_id: str,
    format: str = Query("html", pattern="^(html|json|pdf|md)$"),
    username: str = Query(..., min_length=1, max_length=128),
    lang: str | None = Query(None, pattern="^(zh|en)$"),
):
    """Download search report in the requested format.

    Requires the same trace_id returned by the SSE done event.
    Results are cached for 5 minutes after search completion.
    *lang* overrides the language stored at search time (if provided).
    """
    result, stored_lang = _get_result(trace_id)
    lang = lang or stored_lang
    breach_dates = [r.breach_date for r in result.leak_records if r.breach_date]

    if format == "json":
        content = export_json(
            result.hits, result.profiles, result.clusters,
            username, trace_id=trace_id,
        )
        return Response(
            content=content,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="clawithme_{username}.json"',
            },
        )
    elif format == "pdf":
        content = export_pdf(
            result.hits, result.profiles, result.clusters,
            username, trace_id=trace_id, breach_dates=breach_dates,
        )
        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="clawithme_{username}.pdf"',
            },
        )
    elif format == "md":
        content = export_markdown(
            result.hits, result.profiles, result.clusters,
            username, trace_id=trace_id, breach_dates=breach_dates,
            lang=lang,
        )
        return Response(
            content=content,
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="clawithme_{username}.md"',
            },
        )
    else:  # html
        content = generate_report(
            result.hits, result.profiles, result.clusters,
            username, trace_id=trace_id, breach_dates=breach_dates,
            lang=lang,
        )
        return HTMLResponse(
            content=content,
            headers={
                "Content-Disposition": f'attachment; filename="clawithme_{username}.html"',
            },
        )
