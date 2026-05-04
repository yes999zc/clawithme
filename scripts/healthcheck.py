#!/usr/bin/env python3
"""Health check — verifies core clawithme components are functional.

Usage:
    python scripts/healthcheck.py
    Exit 0 = healthy, Exit 1 = degraded
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from clawithme.engine.http_client import HttpClient
from clawithme.logging import new_trace_id, setup_logging

setup_logging()

checks = {}
trace_id = new_trace_id()

# 1. HTTP client works
try:
    client = HttpClient(timeout_ms=5000, trace_id=trace_id)
    resp = client.get("https://httpbin.org/status/200")
    checks["http_client"] = resp.status_code == 200
except Exception as e:
    checks["http_client"] = False
    print(f"❌ http_client: {e}")

# 2. At least one probeable site returns expected status
try:
    client = HttpClient(timeout_ms=8000, trace_id=trace_id)
    resp = client.get("https://github.com/torvalds")
    checks["github_probe"] = resp.status_code == 200
except Exception as e:
    checks["github_probe"] = False
    print(f"❌ github_probe: {e}")

# 3. Cavalier API reachable (async)
import asyncio


async def check_cavalier():
    from clawithme.leak_sources import CavalierSource
    src = CavalierSource()
    try:
        avail = await src.is_available()
        await src.close()
        return avail
    except Exception:
        return False

checks["cavalier_api"] = asyncio.run(check_cavalier())

# Summary
failed = [k for k, v in checks.items() if not v]
if failed:
    print(f"❌ HEALTHCHECK FAILED: {', '.join(failed)}")
    sys.exit(1)
else:
    print(f"✅ HEALTHY (trace_id={trace_id[:8]})")
    sys.exit(0)
