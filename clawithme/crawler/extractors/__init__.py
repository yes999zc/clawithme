"""Built-in site extractors."""

from clawithme.crawler.extractors.devto import DevtoExtractor
from clawithme.crawler.extractors.github import GithubExtractor
from clawithme.crawler.extractors.gitlab import GitlabExtractor
from clawithme.crawler.extractors.stackoverflow import StackoverflowExtractor
from clawithme.crawler.extractors.v2ex import V2exExtractor
from clawithme.crawler.extractors.bilibili import BilibiliExtractor

__all__ = [
    "BilibiliExtractor",
    "DevtoExtractor",
    "GithubExtractor",
    "GitlabExtractor",
    "StackoverflowExtractor",
    "V2exExtractor",
]
