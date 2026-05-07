"""Per-tier proxy management.

Creates one HttpClient per proxy tier (direct, datacenter, residential)
so that sites with different anti-bot requirements use the right proxy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from clawithme.engine.http_client import HttpClient
from clawithme.logging import get_logger

if TYPE_CHECKING:
    from clawithme.config import Config

logger = get_logger()


class ProxyManager:
    """Manages a pool of HttpClient instances, one per proxy tier.

    Usage::

        pm = ProxyManager(config)
        client = pm.get_client("residential")  # → HttpClient with residential proxy
        client = pm.get_client(None)            # → direct (fallback)
    """

    def __init__(self, config: "Config") -> None:
        timeout = config.scanning.default_timeout_ms
        self._clients: dict[str, HttpClient] = {}

        # Build one HttpClient per configured tier
        tiers = config.proxy.tiers
        if tiers:
            for tier, proxy_url in tiers.items():
                self._clients[tier] = HttpClient(
                    proxy=proxy_url or None,
                    timeout_ms=timeout,
                )
                logger.info("proxy_tier_registered", tier=tier,
                           proxy=proxy_url[:40] + "..." if proxy_url and len(proxy_url) > 40 else proxy_url)

        # Always have a direct (no-proxy) fallback
        if "direct" not in self._clients:
            self._clients["direct"] = HttpClient(timeout_ms=timeout)

        # Backward-compat: if [proxy] http/https is set but tiers aren't,
        # use http as the "datacenter" tier
        if not tiers and config.proxy.http:
            self._clients["datacenter"] = HttpClient(
                proxy=config.proxy.http or None,
                timeout_ms=timeout,
            )
            logger.info("proxy_legacy", url=config.proxy.http)

    def get_client(self, tier: str | None) -> HttpClient:
        """Return the HttpClient for *tier*. Falls back to 'direct'."""
        if tier and tier in self._clients:
            return self._clients[tier]
        return self._clients["direct"]

    def close(self) -> None:
        """Close all managed HttpClient connections."""
        for client in self._clients.values():
            client.close()
