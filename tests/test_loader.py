"""Smoke tests for engine loader."""

import pytest

from clawithme.engine.engines import Engine
from clawithme.engine.loader import get_engine_for_site, load_engines


class TestLoadEngines:
    def test_loads_all_engines(self):
        engines = load_engines()
        assert len(engines) >= 6, f"Expected at least 6 engines, got {len(engines)}"
        assert "base_http_status" in engines
        assert "xenforo" in engines

    def test_all_engines_are_engine_instances(self):
        engines = load_engines()
        for name, engine in engines.items():
            assert isinstance(engine, Engine), f"{name} is not an Engine instance"


class TestGetEngineForSite:
    def test_matches_by_engine_ref(self):
        engines = load_engines()
        site = {"id": "github", "engine_ref": "base_http_status"}
        engine = get_engine_for_site(site, engines)
        assert engine is not None

    def test_returns_none_for_unknown_ref(self):
        engines = load_engines()
        site = {"id": "nonexistent", "engine_ref": "fake_engine"}
        engine = get_engine_for_site(site, engines)
        assert engine is None
