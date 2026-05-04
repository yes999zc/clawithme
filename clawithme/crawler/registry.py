"""Plugin registry — discovers ProfileExtractor implementations via entry_points."""

from __future__ import annotations

from importlib.metadata import entry_points

from clawithme.crawler.base import ProfileExtractor
from clawithme.logging import get_logger

logger = get_logger()


def discover_extractors() -> dict[str, type[ProfileExtractor]]:
    """Discover all installed ProfileExtractor classes.

    Scans entry_points group 'clawithme.extractors'.
    Returns {site_id: ExtractorClass}.
    """
    extractors: dict[str, type[ProfileExtractor]] = {}

    try:
        eps = entry_points(group="clawithme.extractors")
    except TypeError:
        # Python 3.11 compat: entry_points() may need explicit group kwarg
        eps = entry_points().get("clawithme.extractors", [])

    for ep in eps:
        try:
            cls = ep.load()
            if not issubclass(cls, ProfileExtractor):
                logger.warning("not_a_profile_extractor", entry_point=ep.name)
                continue
            if not cls.site_id:
                logger.warning("extractor_no_site_id", entry_point=ep.name)
                continue
            if cls.site_id in extractors:
                existing = extractors[cls.site_id].__name__
                logger.warning(
                    "duplicate_site_id", site_id=cls.site_id,
                    existing=existing, new=cls.__name__,
                )
            extractors[cls.site_id] = cls
            logger.debug("extractor_discovered", site_id=cls.site_id, name=ep.name)
        except (ImportError, TypeError, ValueError) as e:
            logger.warning("extractor_load_failed", entry_point=ep.name, error=str(e))

    logger.info("extractors_discovered", count=len(extractors))
    return extractors
