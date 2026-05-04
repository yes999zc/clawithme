"""Tests for signals/extraction.py — email/phone regex extraction."""

from clawithme.signals.extraction import extract_emails, extract_phones


class TestExtractEmails:
    def test_single_email(self):
        assert extract_emails("contact me at alice@example.com") == ["alice@example.com"]

    def test_multiple_emails(self):
        text = "alice@foo.com and bob@bar.org"
        assert extract_emails(text) == ["alice@foo.com", "bob@bar.org"]

    def test_deduplicate(self):
        assert extract_emails("a@b.com a@b.com") == ["a@b.com"]

    def test_no_email(self):
        assert extract_emails("no email here") == []

    def test_case_insensitive(self):
        assert extract_emails("Alice@Example.COM") == ["alice@example.com"]

    def test_email_in_bio_style_text(self):
        bio = "Full-stack dev | Rust & Python | reach me: dev@mycompany.io"
        assert extract_emails(bio) == ["dev@mycompany.io"]


class TestExtractPhones:
    def test_plain_number(self):
        assert extract_phones("13800001234") == ["13800001234"]

    def test_with_separators(self):
        assert extract_phones("138-0000-1234") == ["13800001234"]
        assert extract_phones("138 0000 1234") == ["13800001234"]

    def test_with_country_code(self):
        assert extract_phones("+86 13800001234") == ["13800001234"]
        assert extract_phones("+8613800001234") == ["13800001234"]

    def test_deduplicate(self):
        assert extract_phones("13800001234 13800001234") == ["13800001234"]

    def test_no_phone(self):
        assert extract_phones("call me maybe") == []

    def test_non_standard_length_skipped(self):
        assert extract_phones("12345") == []
