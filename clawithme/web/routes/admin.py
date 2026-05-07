"""Admin API — runtime proxy configuration management.

Endpoints:
    GET  /api/admin/proxy       — view current proxy tiers
    PUT  /api/admin/proxy       — update proxy tiers (persisted to config.toml)
    POST /api/admin/proxy/test  — test a proxy URL
    GET  /api/admin/proxy/sites — sites grouped by proxy_tier
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from clawithme.cli import load_all_sites
from clawithme.config import ProxyConfig, load_config
from clawithme.logging import get_logger

router = APIRouter(prefix="/api/admin")
logger = get_logger()

# Path to config.toml (relative to project root)
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "config.toml"


class ProxyTierUpdate(BaseModel):
    tiers: dict[str, str]  # tier_name → proxy_url


class ProxyTestRequest(BaseModel):
    url: str  # proxy URL to test


def _serialize_proxy_section(config) -> str:
    """Serialize proxy config to TOML [proxy] section."""
    proxy = config.proxy
    lines = ["[proxy]"]
    lines.append(f'http = "{proxy.http}"')
    lines.append(f'https = "{proxy.https}"')
    lines.append("")
    lines.append("[proxy.tiers]")
    # Write tiers sorted: direct first, then alphabetical
    tiers = proxy.tiers
    for key in sorted(tiers.keys(), key=lambda k: (k != "direct", k)):
        value = tiers[key]
        # Escape backslashes and double quotes in values
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        lines.append(f'{key} = "{escaped}"')
    return "\n".join(lines) + "\n"


def _write_proxy_config(config) -> None:
    """Persist proxy config to config.toml, preserving other sections."""
    path = _CONFIG_PATH
    new_section = _serialize_proxy_section(config)

    if not path.exists():
        path.write_text(new_section + "\n")
        logger.info("config_created", path=str(path))
        return

    content = path.read_text()

    # Replace existing [proxy]...[next_section] or [proxy]...EOF
    pattern = r"^\[proxy\].*?(?=^\[|$)"
    if re.search(pattern, content, re.MULTILINE | re.DOTALL):
        new_content = re.sub(
            pattern, new_section.rstrip("\n"), content,
            flags=re.MULTILINE | re.DOTALL,
        )
    else:
        # No existing [proxy] section — append
        new_content = content.rstrip() + "\n\n" + new_section

    new_content = new_content.replace(
        "# ── Deprecated (kept for backward compatibility) ──\n", ""
    ).replace(
        "# Single proxy for all sites. Use [proxy.tiers] instead.\n", ""
    )

    # Ensure the [proxy.tiers] block looks right
    # Find [proxy.tiers] and verify it's clean
    if "[proxy.tiers]" not in new_content:
        new_content += "\n[proxy.tiers]\n"

    path.write_text(new_content)
    logger.info("proxy_config_saved", path=str(path))


# ═══════════════════════════════════════════════════════════════
# Routes
# ═══════════════════════════════════════════════════════════════


@router.get("/proxy")
async def get_proxy_config(request: Request):
    """Return current proxy configuration."""
    cfg = load_config()
    return {
        "http": cfg.proxy.http,
        "https": cfg.proxy.https,
        "tiers": cfg.proxy.tiers,
    }


@router.put("/proxy")
async def update_proxy_config(body: ProxyTierUpdate, request: Request):
    """Update proxy tiers. Writes to config.toml immediately."""
    cfg = load_config()
    cfg.proxy.tiers = body.tiers
    try:
        _write_proxy_config(cfg)
    except OSError as e:
        logger.error("proxy_config_write_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to write config: {e}")
    logger.info("proxy_tiers_updated", tiers=list(body.tiers.keys()))
    return {"status": "ok", "tiers": body.tiers}


@router.post("/proxy/test")
async def test_proxy(body: ProxyTestRequest):
    """Test a proxy URL by making a request through it."""
    if not body.url:
        return {"status": "ok", "note": "direct connection (no proxy)"}

    from clawithme.engine.http_client import HttpClient

    client = HttpClient(proxy=body.url, timeout_ms=10000)
    try:
        # Use a fast, reliable endpoint
        resp = await asyncio.to_thread(
            client.get, "https://httpbin.org/ip"
        )
        if resp.status_code == 200:
            ip_info = resp.text.strip()
            return {
                "status": "ok",
                "code": resp.status_code,
                "ip": ip_info,
                "note": f"Proxy working — outgoing IP: {ip_info}",
            }
        return {
            "status": "error",
            "code": resp.status_code,
            "note": f"Unexpected status {resp.status_code}",
        }
    except (OSError, TimeoutError, ValueError) as e:
        return {"status": "error", "note": str(e)}
    finally:
        client.close()


@router.get("/proxy/sites")
async def get_sites_by_tier(request: Request):
    """Return sites grouped by proxy_tier (for reference)."""
    sites = load_all_sites(include_migrated=False)
    by_tier: dict[str, list[str]] = {"(not set)": []}
    for site in sites:
        tier = site.get("proxy_tier") or "(not set)"
        by_tier.setdefault(tier, []).append(site["id"])
    return {tier: sorted(ids) for tier, ids in by_tier.items()}


@router.get("/linkedin/cookies")
async def get_linkedin_cookie_status(request: Request):
    """Return LinkedIn cookie status (configured, file exists, count, age)."""
    import os
    import time
    from pathlib import Path

    cfg = load_config()
    cookie_file = cfg.apis.linkedin_cookie_file

    if not cookie_file:
        return {
            "configured": False,
            "note": "未配置 Cookie，运行 clawithme linkedin-login 进行登录",
        }

    path = Path(cookie_file).expanduser()
    if not path.exists():
        return {
            "configured": True,
            "file": str(path),
            "exists": False,
            "note": "Cookie 文件不存在，运行 clawithme linkedin-login 重新登录",
        }

    try:
        data = json.loads(path.read_text())
        count = len(data) if isinstance(data, list) else 0
        mtime = path.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        return {
            "configured": True,
            "file": str(path),
            "exists": True,
            "cookie_count": count,
            "age_days": round(age_days, 1),
            "fresh": age_days < 14,
            "note": (
                f"{count} 个 Cookie · {age_days:.0f} 天前"
                if age_days < 14
                else f"{count} 个 Cookie · {age_days:.0f} 天前（可能已过期，建议重新登录）"
            ),
        }
    except (OSError, json.JSONDecodeError) as e:
        return {
            "configured": True,
            "file": str(path),
            "exists": True,
            "error": str(e),
            "note": "Cookie 文件读取失败",
        }
