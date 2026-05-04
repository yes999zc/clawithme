"""Tests for plugin registry."""

from clawithme.crawler.registry import discover_extractors


def test_discover_extractors_returns_dict():
    result = discover_extractors()
    assert isinstance(result, dict)


def test_discover_finds_zhihu_extractor():
    result = discover_extractors()
    assert "zhihu" in result, f"Expected zhihu in {list(result.keys())}"
