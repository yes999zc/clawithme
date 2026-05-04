"""Smoke tests for CLI entry point."""

import pytest
from clawithme.cli import load_all_sites


class TestLoadAllSites:
    def test_returns_non_empty_list(self):
        sites = load_all_sites()
        assert len(sites) > 0, "No sites loaded"

    def test_all_sites_have_id(self):
        sites = load_all_sites()
        for site in sites:
            assert "id" in site, f"Site missing 'id': {site}"

    def test_no_deprecated_sites(self):
        sites = load_all_sites()
        for site in sites:
            assert not site.get("deprecated", False), (
                f"Site {site['id']} is deprecated but was loaded"
            )
