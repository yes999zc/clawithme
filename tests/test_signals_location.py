"""Tests for clawithme.signals.location."""

import pytest

from clawithme.signals.location import compare_locations


class TestCompareLocations:
    def test_exact_match_english(self):
        assert compare_locations("San Francisco", "San Francisco") == 0.35

    def test_chinese_english_normalization(self):
        assert compare_locations("北京", "Beijing") == 0.35
        assert compare_locations("上海", "Shanghai") == 0.35
        assert compare_locations("广州", "Guangzhou") == 0.35

    def test_substring_match(self):
        assert compare_locations("San Francisco, CA", "San Francisco") == 0.15
        assert compare_locations("San Francisco", "San Francisco, CA") == 0.15

    def test_no_match(self):
        assert compare_locations("New York", "London") == 0.0

    def test_none_or_empty(self):
        assert compare_locations(None, "Beijing") == 0.0
        assert compare_locations("Beijing", None) == 0.0
        assert compare_locations("", "Beijing") == 0.0
        assert compare_locations("  ", "Beijing") == 0.0
        assert compare_locations(None, None) == 0.0

    def test_chinese_city_name_in_context(self):
        # "北京海淀" should match "Beijing" because "北京" → "beijing" normalization
        assert compare_locations("北京海淀", "Beijing") == 0.15

    def test_full_chinese_address_match(self):
        assert compare_locations("中国北京", "北京") == 0.15
