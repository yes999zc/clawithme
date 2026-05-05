"""LeakSource manager — queries multiple breach sources with priority and fallback.

Supports:
- Parallel querying across sources
- Per-source timeout
- Graceful error handling (one source fails → others continue)
- Deduplication by email
"""

from __future__ import annotations

import asyncio

from clawithme.leak_sources import BreachRecord, LeakSource
from clawithme.logging import get_logger

logger = get_logger()

# Default timeout per source (seconds)
DEFAULT_SOURCE_TIMEOUT = 15


def _deduplicate(records: list[BreachRecord]) -> list[BreachRecord]:
    """Remove duplicate records by (email, source) key."""
    seen: set[tuple[str, str]] = set()
    result: list[BreachRecord] = []
    for r in records:
        key = (r.email or "", r.source or "")
        if key not in seen:
            seen.add(key)
            result.append(r)
    return result


async def _query_source(
    source: LeakSource,
    username: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    timeout: float = DEFAULT_SOURCE_TIMEOUT,
) -> list[BreachRecord]:
    """Query a single source with timeout. Returns empty list on failure."""
    source_name = type(source).__name__

    async def _do_query() -> list[BreachRecord]:
        if email:
            return await source.search_by_email(email)
        if phone:
            return await source.search_by_phone(phone)
        if username:
            return await source.search_by_username(username)
        return []

    try:
        return await asyncio.wait_for(_do_query(), timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("leak_source_timeout", source=source_name,
                       username=username, email=email)
        return []
    except (OSError, ValueError) as e:
        logger.warning("leak_source_error", source=source_name,
                       username=username, email=email, error=str(e))
        return []


async def query_breaches(
    sources: list[LeakSource],
    *,
    username: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    timeout: float = DEFAULT_SOURCE_TIMEOUT,
) -> list[BreachRecord]:
    """Query all sources in parallel, merge and deduplicate results.

    At least one of username/email/phone must be provided.
    Returns combined deduplicated records from all sources.
    Sources that fail or timeout are logged and skipped.
    """
    if not sources:
        return []

    tasks = [
        _query_source(s, username=username, email=email, phone=phone, timeout=timeout)
        for s in sources
    ]
    results = await asyncio.gather(*tasks)
    all_records: list[BreachRecord] = []
    for r in results:
        all_records.extend(r)
    return _deduplicate(all_records)
