"""Integration tests for the probe → extract pipeline."""

from unittest.mock import MagicMock, patch

from clawithme.crawler.extractors.github import GithubExtractor
from clawithme.crawler.registry import discover_extractors


class TestExtractionPipeline:
    def test_discover_finds_github_extractor(self):
        extractors = discover_extractors()
        assert "github" in extractors, f"Expected github in {list(extractors)}"
        assert issubclass(extractors["github"], GithubExtractor)

    def test_extractor_dispatch(self):
        """Simulate CLI: hit site → match extractor → call extract()."""
        extractors = discover_extractors()

        # Simulate a site hit
        site_def = {"id": "github", "name": "GitHub"}
        username = "testuser"

        extractor_cls = extractors.get(site_def["id"])
        assert extractor_cls is not None, "No extractor for github"

        extractor = extractor_cls()

        with patch(
            "clawithme.crawler.extractors.github.CrawlerClient.fetch_static"
        ) as mock_fetch:
            mock_page = MagicMock()
            mock_page.status = 200
            mock_page.url = "https://github.com/testuser"
            mock_page.text = "mock"
            mock_page.css.return_value = []
            mock_fetch.return_value = mock_page

            profile = extractor.extract(site_def, username)

        assert profile.site_id == "github"
        assert profile.username == "testuser"
        mock_fetch.assert_called_once()

    def test_extractor_not_found_for_unknown_site(self):
        extractors = discover_extractors()
        assert "hupu" not in extractors
