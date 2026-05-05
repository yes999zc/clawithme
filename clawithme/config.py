"""Configuration loader — reads config.toml and exposes typed settings.

Uses stdlib tomllib (Python 3.11+) — no external dependency.
Falls back gracefully if config file is missing.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import structlog


@dataclass
class ProxyConfig:
    http: str = ""
    https: str = ""


@dataclass
class ApiConfig:
    hibp_api_key: str = ""
    dehashed_api_key: str = ""
    dehashed_email: str = ""


@dataclass
class ScanningConfig:
    default_timeout_ms: int = 5000
    max_concurrency: int = 10
    min_interval_ms: int = 500


@dataclass
class LoggingConfig:
    level: str = "INFO"


@dataclass
class Config:
    """Typed configuration loaded from config.toml."""

    proxy: ProxyConfig = field(default_factory=ProxyConfig)
    apis: ApiConfig = field(default_factory=ApiConfig)
    scanning: ScanningConfig = field(default_factory=ScanningConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def load_config(path: str | Path | None = None) -> Config:
    """Load configuration from config.toml.

    Looks for config.toml in:
    1. Explicit path (if provided)
    2. Project root (clawithme/../config.toml)
    3. Falls back to defaults if file not found

    Returns Config with defaults for any missing fields.
    """
    config = Config()

    if path is None:
        # Look in project root relative to this file
        project_root = Path(__file__).resolve().parent.parent
        path = project_root / "config.toml"

    toml_path = Path(path)
    if not toml_path.exists():
        return config  # silent fallback — use defaults

    try:
        raw = tomllib.loads(toml_path.read_text())
    except (OSError, ValueError) as e:
        # Corrupted config — warn but don't crash
        logger = structlog.get_logger()
        logger.warning("config_parse_failed", path=str(toml_path), error=str(e))
        return config

    # Proxy
    proxy_raw = raw.get("proxy", {})
    config.proxy = ProxyConfig(
        http=proxy_raw.get("http", ""),
        https=proxy_raw.get("https", ""),
    )

    # APIs
    apis_raw = raw.get("apis", {})
    config.apis = ApiConfig(
        hibp_api_key=apis_raw.get("hibp_api_key", ""),
        dehashed_api_key=apis_raw.get("dehashed_api_key", ""),
        dehashed_email=apis_raw.get("dehashed_email", ""),
    )

    # Scanning
    scan_raw = raw.get("scanning", {})
    config.scanning = ScanningConfig(
        default_timeout_ms=scan_raw.get("default_timeout_ms", 5000),
        max_concurrency=scan_raw.get("max_concurrency", 10),
        min_interval_ms=scan_raw.get("min_interval_ms", 500),
    )

    # Logging
    log_raw = raw.get("logging", {})
    config.logging = LoggingConfig(
        level=log_raw.get("level", "INFO"),
    )

    return config
