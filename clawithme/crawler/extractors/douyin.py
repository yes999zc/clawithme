"""抖音 (Douyin) profile extractor — TikHub API.

Pipeline (2 API calls):
  1. POST /api/v1/douyin/search/fetch_user_search_v2  → 获取 sec_uid
  2. GET  /api/v1/douyin/app/v3/handler_user_profile   → 获取用户详情

Requires TIKHUB_API_TOKEN environment variable.
"""

from __future__ import annotations

import json
import os
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.logging import get_logger

logger = get_logger()

TIKHUB_BASE = "https://api.tikhub.io"


class DouyinExtractor(ProfileExtractor):
    """通过 TikHub API 提取抖音用户资料。"""

    site_id = "douyin"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        token = os.environ.get("TIKHUB_API_TOKEN")
        if not token:
            logger.warning("douyin_no_token", msg="TIKHUB_API_TOKEN not set")
            return Profile(
                site_id=self.site_id,
                site_name=site.get("name", "抖音"),
                url=f"https://www.douyin.com/user/{username}",
                username=username,
            )

        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "抖音"),
            url=f"https://www.douyin.com/user/{username}",
            username=username,
        )
        auth_header = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # ── Step 1: 搜索用户，获取 sec_uid ──
        sec_uid = self._search_user(username, auth_header)
        if not sec_uid:
            logger.debug("douyin_user_not_found", keyword=username)
            return profile

        # ── Step 2: 获取用户详情 ──
        self._fetch_profile(sec_uid, profile, auth_header)

        return profile

    def _search_user(self, keyword: str, auth_header: dict) -> str | None:
        """搜索用户并返回第一个结果的 sec_uid (user_id)。"""
        url = f"{TIKHUB_BASE}/api/v1/douyin/search/fetch_user_search_v2"
        body = json.dumps({"keyword": keyword}).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=body, headers={**auth_header, "User-Agent": "clawithme/1.0"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            user_list = data.get("data", {}).get("data", {}).get("user_list", [])
            if user_list and user_list[0].get("user_id"):
                return user_list[0]["user_id"]
            return None
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("douyin_search_failed", keyword=keyword, error=str(e))
            return None

    def _fetch_profile(self, sec_uid: str, profile: Profile, auth_header: dict) -> None:
        """获取用户详情并填充 Profile。"""
        url = f"{TIKHUB_BASE}/api/v1/douyin/app/v3/handler_user_profile?sec_user_id={sec_uid}"

        try:
            # 此端点使用 GET，不需要 Content-Type
            get_headers = {"Authorization": auth_header["Authorization"]}
            req = urllib.request.Request(url, headers={**get_headers, "User-Agent": "clawithme/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())

            user = data.get("data", {}).get("user", {})
            if not user:
                logger.debug("douyin_profile_empty", sec_uid=sec_uid)
                return

            # ── 字段映射 ──
            profile.display_name = user.get("nickname") or None
            profile.bio = user.get("signature") or None
            profile.location = user.get("ip_location") or None
            profile.post_count = _to_int(user.get("aweme_count"))
            profile.follower_count = _to_int(user.get("follower_count"))
            profile.following_count = _to_int(user.get("following_count"))

            # 抖音号 (unique_id) 作为 username 字段
            douyin_id = user.get("unique_id")
            if douyin_id:
                profile.username = douyin_id

            # 头像: avatar_larger.url_list[0]
            avatar_larger = user.get("avatar_larger", {})
            avatar_urls = avatar_larger.get("url_list", [])
            if avatar_urls:
                profile.avatar_url = avatar_urls[0]

            # 主页链接
            share_info = user.get("share_info", {})
            share_url = share_info.get("share_url")
            if share_url:
                profile.url = share_url

            # 额外信息
            profile.extra = {
                "sec_uid": user.get("sec_uid"),
                "uid": user.get("uid"),
                "user_age": user.get("user_age"),
                "gender": user.get("gender"),  # 0=未知, 1=男, 2=女
            }

        except (OSError, json.JSONDecodeError) as e:
            logger.debug("douyin_profile_failed", sec_uid=sec_uid, error=str(e))


def _to_int(val) -> int | None:
    """安全转换为整数，失败返回 None。"""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
