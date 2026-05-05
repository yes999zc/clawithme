"""Tests for clawithme.cache — ResultCache TTL-based SQLite cache."""

import time
from pathlib import Path

import pytest

from clawithme.cache import ResultCache


@pytest.fixture
def cache(tmp_path: Path) -> ResultCache:
    """Create a cache in a temporary directory."""
    return ResultCache(cache_dir=tmp_path)


class TestResultCache:
    def test_get_set(self, cache: ResultCache) -> None:
        cache.set("key1", {"result": 42})
        result = cache.get("key1")
        assert result == {"result": 42}

    def test_cache_miss(self, cache: ResultCache) -> None:
        assert cache.get("nonexistent") is None

    def test_ttl_expiration(self, cache: ResultCache) -> None:
        cache.set("expires", {"x": 1}, ttl_seconds=0)
        time.sleep(0.01)  # Let it expire
        assert cache.get("expires") is None

    def test_invalidate(self, cache: ResultCache) -> None:
        cache.set("remove_me", {"a": 1})
        assert cache.get("remove_me") is not None
        cache.invalidate("remove_me")
        assert cache.get("remove_me") is None

    def test_overwrite(self, cache: ResultCache) -> None:
        cache.set("key", {"v": 1})
        cache.set("key", {"v": 2})
        assert cache.get("key") == {"v": 2}

    def test_clear(self, cache: ResultCache) -> None:
        cache.set("a", {"x": 1})
        cache.set("b", {"x": 2})
        cache.clear()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_nested_dict(self, cache: ResultCache) -> None:
        value = {"nested": {"deep": [1, 2, 3]}}
        cache.set("nested", value)
        assert cache.get("nested") == value
