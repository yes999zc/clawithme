"""Discord profile extractor via bot API.

API: GET https://discord.com/api/v10/users/{user_id}
Requires DISCORD_BOT_TOKEN environment variable.
Input is a Discord User ID (numeric string), NOT a display username.
"""

from __future__ import annotations

import json
import os
import urllib.request

from clawithme.crawler.base import Profile, ProfileExtractor
from clawithme.logging import get_logger

logger = get_logger()


class DiscordExtractor(ProfileExtractor):
    """Extract public profile data from Discord via bot API."""

    site_id = "discord"
    requires_dynamic = False

    def extract(self, site: dict, username: str) -> Profile:
        """Extract profile for a Discord user ID.

        Args:
            site: Site definition dict (from site JSON).
            username: Discord User ID (numeric string, e.g. "123456789").

        Returns:
            Profile with available fields populated.
        """
        token = os.environ.get("DISCORD_BOT_TOKEN")
        profile = Profile(
            site_id=self.site_id,
            site_name=site.get("name", "Discord"),
            url=f"https://discord.com/users/{username}",
            username=username,
        )

        if token is None:
            logger.debug("discord_no_token", user_id=username)
            return profile

        api_url = f"https://discord.com/api/v10/users/{username}"

        try:
            req = urllib.request.Request(
                api_url,
                headers={
                    "Authorization": f"Bot {token}",
                    "User-Agent": "clawithme/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read())

            # Display name: prefer global_name (server display name),
            # fall back to username.
            profile.display_name = data.get("global_name") or data.get("username") or None

            # Avatar URL
            avatar_hash = data.get("avatar")
            if avatar_hash:
                fmt = "gif" if avatar_hash.startswith("a_") else "png"
                profile.avatar_url = (
                    f"https://cdn.discordapp.com/avatars/{username}/{avatar_hash}.{fmt}?size=512"
                )

            # Banner URL
            banner_hash = data.get("banner")
            if banner_hash:
                fmt = "gif" if banner_hash.startswith("a_") else "png"
                # Store banner in extra; Profile has no dedicated banner field
                if profile.extra is None:
                    profile.extra = {}
                profile.extra["banner_url"] = (
                    f"https://cdn.discordapp.com/banners/{username}/{banner_hash}.{fmt}?size=512"
                )

            # Bio
            profile.bio = data.get("bio") or None

            # Extra fields
            extra_fields = {}
            accent_color = data.get("accent_color")
            if accent_color is not None:
                extra_fields["accent_color"] = accent_color

            public_flags = data.get("public_flags")
            if public_flags is not None:
                extra_fields["public_flags"] = public_flags

            avatar_decoration = data.get("avatar_decoration_data")
            if avatar_decoration is not None:
                extra_fields["avatar_decoration"] = avatar_decoration

            # Merge with existing extra (banner_url may already be set)
            if extra_fields:
                if profile.extra is None:
                    profile.extra = extra_fields
                else:
                    profile.extra.update(extra_fields)

        except (OSError, json.JSONDecodeError) as e:
            logger.debug("discord_api_failed", user_id=username, error=str(e))

        return profile
