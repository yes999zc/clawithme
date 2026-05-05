"""Simple TTL-based disk cache using SQLite.

No external dependencies — uses stdlib sqlite3.
Values are JSON-serialized dicts with expiration timestamps.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class ResultCache:
    """TTL-based disk cache backed by SQLite.

    Thread-safe for concurrent reads. The cache file is created
    at ``cache_dir / cache.db`` on first use.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "clawithme"
        self._db_path = Path(cache_dir) / "cache.db"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS cache ("
                "  key TEXT PRIMARY KEY,"
                "  value TEXT,"
                "  expires_at REAL"
                ")"
            )

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self._db_path), check_same_thread=False
            )
        return self._conn

    def close(self) -> None:
        """Close the persistent connection. Safe to call multiple times."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def get(self, key: str) -> dict | None:
        """Return cached dict or None if expired or missing."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT value, expires_at FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        value_json, expires_at = row
        if time.time() > expires_at:
            self.invalidate(key)
            return None
        return json.loads(value_json)

    def set(self, key: str, value: dict, ttl_seconds: int = 86400) -> None:
        """Store *value* (dict) with a TTL in seconds (default 24h)."""
        expires_at = time.time() + ttl_seconds
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) "
                "VALUES (?, ?, ?)",
                (key, json.dumps(value), expires_at),
            )

    def invalidate(self, key: str) -> None:
        """Remove a single cache entry."""
        with self._connect() as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))

    def clear(self) -> None:
        """Remove all cache entries."""
        with self._connect() as conn:
            conn.execute("DELETE FROM cache")
