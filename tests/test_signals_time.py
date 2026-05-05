"""Tests for signals/time.py — joined_date correlation signal."""

from clawithme.signals.time import compare_joined_dates


class TestCompareJoinedDates:
    def test_same_month_and_year(self):
        assert compare_joined_dates("2018-03-15", "2018-03-01") == 0.40
        assert compare_joined_dates("2018-03", "March 2018") == 0.40

    def test_within_plusminus_3_months(self):
        assert compare_joined_dates("2018-01", "2018-04") == 0.20
        assert compare_joined_dates("2018-04", "2018-01") == 0.20
        assert compare_joined_dates("Mar 2018", "2018-06") == 0.20

    def test_same_year_only(self):
        assert compare_joined_dates("2018", "2018-06") == 0.10
        assert compare_joined_dates("2018", "2018") == 0.10
        assert compare_joined_dates("2018-01", "2018-06") == 0.10  # >3mo apart

    def test_different_years(self):
        assert compare_joined_dates("2018-03", "2019-03") == 0.0
        assert compare_joined_dates("2018", "2020") == 0.0

    def test_none_or_empty(self):
        assert compare_joined_dates(None, "2018-03") == 0.0
        assert compare_joined_dates("2018-03", None) == 0.0
        assert compare_joined_dates("", "2018-03") == 0.0
        assert compare_joined_dates("  ", "2018-03") == 0.0
        assert compare_joined_dates(None, None) == 0.0

    def test_unparseable(self):
        assert compare_joined_dates("invalid", "2018-03") == 0.0
