# Architecture Isolation — Implementation Plan

> **For Hermes:** Execute task-by-task in order.

**Goal:** Create `clawithme-cn` plugin repo, wire up plugin discovery in main repo, ship first extractor skeleton.

**Architecture:** Main repo defines `ProfileExtractor` ABC + `registry.py` (importlib.metadata entry_points). `clawithme-cn` implements CN site extractors as installable plugins. Runtime auto-discovers all installed extractors.

**Tech Stack:** Pure Python 3.11+, `importlib.metadata` (stdlib), no new deps.

---

### Task 1: Create Profile dataclass + ProfileExtractor ABC

**Objective:** Define the data model and abstract interface for all extractors.

**Files:**
- Create: `clawithme/crawler/base.py`

**Step 1: Write the module**

```python
"""Crawler base — Profile dataclass and ProfileExtractor ABC."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Profile:
    """Unified profile data extracted from a single site.

    All fields optional — different sites expose different data.
    """
    site_id: str
    site_name: str
    url: str
    username: str
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None
    avatar_hash: str | None = None  # sha256 of avatar image
    location: str | None = None
    joined_date: str | None = None
    post_count: int | None = None
    follower_count: int | None = None
    following_count: int | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def empty(self) -> bool:
        """True if no meaningful data beyond site id/name/url/username."""
        return not any([
            self.display_name, self.bio, self.avatar_url,
            self.location, self.joined_date, self.post_count,
            self.follower_count, self.extra,
        ])


class ProfileExtractor(ABC):
    """Abstract base for site-specific profile crawlers.

    Each extractor handles ONE site. Registered via entry_points.
    """

    # Must be set by subclass
    site_id: str = ""

    @abstractmethod
    def can_handle(self, site: dict) -> bool:
        """Return True if this extractor can handle the given site dict."""
        ...

    @abstractmethod
    def extract(self, site: dict, username: str) -> Profile:
        """Crawl the site and return a Profile."""
        ...
```

**Step 2: Verify import**

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
python -c "from clawithme.crawler.base import Profile, ProfileExtractor; print('OK')"
```

---

### Task 2: Create Plugin Registry

**Objective:** discovery mechanism that finds all installed extractors via entry_points.

**Files:**
- Create: `clawithme/crawler/registry.py`

**Step 1: Write the module**

```python
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
        # Python 3.11 compat: entry_points() may need explicit group
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
            extractors[cls.site_id] = cls
            logger.debug("extractor_discovered", site_id=cls.site_id, name=ep.name)
        except Exception as e:
            logger.warning("extractor_load_failed", entry_point=ep.name, error=str(e))

    logger.info("extractors_discovered", count=len(extractors))
    return extractors
```

**Step 2: Verify import**

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
python -c "from clawithme.crawler.registry import discover_extractors; print(len(discover_extractors()), 'extractors')"
```

Expected: `0 extractors` (no plugins installed yet).

---

### Task 3: Update crawler/__init__.py

**Objective:** Expose public API from crawler package.

**Files:**
- Modify: `clawithme/crawler/__init__.py`

**Step 1: Replace stub with real exports**

```python
"""Phase 3 — Deep crawler: profile extraction framework."""

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.crawler.registry import discover_extractors

__all__ = ["Profile", "ProfileExtractor", "discover_extractors"]
```

**Step 2: Verify**

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
python -c "from clawithme.crawler import Profile, ProfileExtractor, discover_extractors; print('OK')"
```

---

### Task 4: Create clawithme-cn Repo

**Objective:** Create the plugin repository on GitHub with skeleton structure.

**Step 1: Create repo via gh CLI**

```bash
gh repo create clawithme-cn --public --description "China site extractors for clawithme OSINT tool" --clone
```

**Step 2: Create directory structure**

```
clawithme-cn/
├── extractors/
│   └── __init__.py
├── pyproject.toml
├── README.md
└── LICENSE
```

**Step 3: Write pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "clawithme-cn"
version = "0.1.0"
description = "China site extractors for clawithme OSINT tool"
requires-python = ">=3.11"
license = {text = "MIT"}
dependencies = [
    "clawithme>=0.1.0",
    "scrapling>=0.4",
]

[project.entry-points."clawithme.extractors"]
zhihu = "clawithme_cn.extractors.zhihu:ZhihuExtractor"

[tool.setuptools.packages.find]
where = ["."]
```

**Step 4: Write README.md**

```markdown
# clawithme-cn

China site extractors for [clawithme](https://github.com/yes999zc/clawithme).

## Install

pip install git+https://github.com/yes999zc/clawithme-cn.git

## Extractors

| Site | Extractor | Status |
|------|-----------|--------|
| 知乎 | ZhihuExtractor | planned |
| B站 | BilibiliExtractor | planned |
| 微博 | WeiboExtractor | planned |
| ... | ... | ... |
```

**Step 5: Push**

---

### Task 5: Write First Extractor Skeleton (zhihu)

**Objective:** One working extractor to validate the plugin pipeline end-to-end.

**Files:**
- Create: `extractors/zhihu.py` (in clawithme-cn repo)

**Step 1: Write skeleton**

```python
"""Zhihu profile extractor."""

from __future__ import annotations

from clawithme.crawler.base import Profile, ProfileExtractor


class ZhihuExtractor(ProfileExtractor):
    """Extract public profile data from 知乎."""

    site_id = "zhihu"

    def can_handle(self, site: dict) -> bool:
        return site.get("id") == "zhihu"

    def extract(self, site: dict, username: str) -> Profile:
        profile = Profile(
            site_id="zhihu",
            site_name=site.get("name", "知乎"),
            url=f"https://www.zhihu.com/people/{username}",
            username=username,
        )
        # TODO: Phase 3.1.2 — actual scraping logic
        return profile
```

**Step 2: Verify import**

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme-cn
pip install -e .
python -c "from extractors.zhihu import ZhihuExtractor; print(ZhihuExtractor.site_id)"
```

---

### Task 6: Wire Up Plugin Discovery in Main Repo

**Objective:** Install clawithme-cn into main repo's venv and verify discovery.

**Step 1: Install clawithme-cn as editable**

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
pip install -e ../clawithme-cn
```

**Step 2: Verify discovery**

```bash
python -c "
from clawithme.crawler.registry import discover_extractors
extractors = discover_extractors()
print(f'Found {len(extractors)} extractors')
for sid, cls in extractors.items():
    print(f'  {sid}: {cls.__name__}')
"
```

Expected: `Found 1 extractors: zhihu: ZhihuExtractor`

---

### Task 7: Add Tests + Validate

**Objective:** Test the base classes and registry.

**Files:**
- Create: `tests/test_crawler_base.py` (in clawithme repo)
- Create: `tests/test_crawler_registry.py` (in clawithme repo)

**Step 1: test_crawler_base.py**

```python
"""Tests for crawler base classes."""

from clawithme.crawler.base import Profile, ProfileExtractor


class TestProfile:
    def test_empty_profile_is_empty(self):
        p = Profile(site_id="test", site_name="Test", url="http://x", username="u")
        assert p.empty is True

    def test_profile_with_display_name_not_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x", username="u", display_name="U")
        assert p.empty is False

    def test_extra_dict_defaults_empty(self):
        p = Profile(site_id="t", site_name="T", url="http://x", username="u")
        assert p.extra == {}


class FakeExtractor(ProfileExtractor):
    site_id = "fake"

    def can_handle(self, site: dict) -> bool:
        return site.get("id") == "fake"

    def extract(self, site: dict, username: str) -> Profile:
        return Profile(site_id="fake", site_name="Fake", url="http://x", username=username)


class TestProfileExtractor:
    def test_fake_extractor_can_handle(self):
        ex = FakeExtractor()
        assert ex.can_handle({"id": "fake"}) is True
        assert ex.can_handle({"id": "other"}) is False

    def test_fake_extractor_extract(self):
        ex = FakeExtractor()
        profile = ex.extract({"id": "fake", "name": "Fake"}, "testuser")
        assert profile.site_id == "fake"
        assert profile.username == "testuser"
```

**Step 2: test_crawler_registry.py**

```python
"""Tests for plugin registry."""

from clawithme.crawler.registry import discover_extractors


def test_discover_extractors_returns_dict():
    result = discover_extractors()
    assert isinstance(result, dict)
```

**Step 3: Run all tests**

```bash
cd ~/AI_Workspace/01_Code/tools/clawithme
python -m pytest tests/ -v
```

Expected: all tests pass (23+ including new ones).

---

### Task 8: Commit + Push Both Repos
