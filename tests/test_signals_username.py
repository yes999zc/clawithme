"""Tests for signals/username.py — username similarity comparison."""

from clawithme.signals.username import compare_usernames, levenshtein_distance


class TestLevenshtein:
    def test_identical(self):
        assert levenshtein_distance("alice", "alice") == 0

    def test_single_substitution(self):
        assert levenshtein_distance("alice", "alica") == 1

    def test_single_insertion(self):
        assert levenshtein_distance("alice", "alicee") == 1

    def test_single_deletion(self):
        assert levenshtein_distance("alice", "alic") == 1

    def test_completely_different(self):
        assert levenshtein_distance("alice", "bob123") > 3

    def test_empty(self):
        assert levenshtein_distance("", "abc") == 3
        assert levenshtein_distance("abc", "") == 3


class TestCompareUsernames:
    def test_exact_match(self):
        assert compare_usernames("alice", "alice") == 1.0

    def test_case_insensitive(self):
        assert compare_usernames("Alice", "alice") == 1.0

    def test_affix_variation(self):
        assert compare_usernames("alice", "alice_cn") == 0.85
        assert compare_usernames("alice_dev", "alice") == 0.85

    def test_digit_suffix(self):
        assert compare_usernames("alice42", "alice") == 0.8
        assert compare_usernames("alice", "alice123") == 0.8

    def test_levenshtein_similar(self):
        sim = compare_usernames("alice", "alica")
        assert 0.5 < sim < 0.8  # close but not identical

    def test_completely_different(self):
        assert compare_usernames("alice", "bob123") == 0.0

    def test_empty_handled(self):
        assert compare_usernames("", "alice") == 0.0
        assert compare_usernames("alice", "   ") == 0.0
