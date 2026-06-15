"""Instagram collector via Meta Graph API."""
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.social.base import BaseSocialCollector, SocialPostData


def parse_media(data: dict[str, Any]) -> list[SocialPostData]:
    """Parse Instagram media data from hashtag flow.

    Args:
        data: JSON response dict containing data array from Graph API

    Returns:
        List of SocialPostData objects extracted from the response
    """
    posts: list[SocialPostData] = []

    for media in data.get("data", []):
        try:
            caption = media.get("caption", "")
            if not caption:
                continue

            post_url = media.get("permalink")
            timestamp_str = media.get("timestamp")

            posted_at: datetime | None = None
            if timestamp_str:
                try:
                    posted_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            posts.append(
                SocialPostData(
                    platform="instagram",
                    post_url=post_url,
                    content=caption,
                    posted_at=posted_at,
                )
            )
        except Exception:
            continue

    return posts


class InstagramCollector(BaseSocialCollector):
    """Collect posts from Instagram via Meta Graph API."""

    PLATFORM = "instagram"
    RATE_LIMIT_SEC = 1.0

    async def collect(self, query: str) -> list[SocialPostData]:
        """Collect Instagram posts via hashtag search."""
        posts: list[SocialPostData] = []

        if not settings.instagram_access_token:
            return posts

        try:
            await self._wait_rate_limit()

            # Strip spaces from query for hashtag
            hashtag_query = query.replace(" ", "")

            # Search for hashtag
            params = {
                "user_id": "17841401062180",  # Instagram Business Account ID (can be dynamic)
                "q": hashtag_query,
                "access_token": settings.instagram_access_token,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Get hashtag ID
                resp = await client.get(
                    "https://graph.facebook.com/v21.0/ig_hashtag_search",
                    params=params,
                )
                resp.raise_for_status()

                hashtag_data = resp.json()
                hashtag_id = None

                if hashtag_data.get("data"):
                    hashtag_id = hashtag_data["data"][0].get("id")

                if not hashtag_id:
                    return posts

                await self._wait_rate_limit()

                # Get recent media for hashtag
                media_params = {
                    "fields": "id,caption,permalink,timestamp",
                    "access_token": settings.instagram_access_token,
                }

                resp = await client.get(
                    f"https://graph.facebook.com/v21.0/{hashtag_id}/recent_media",
                    params=media_params,
                )
                resp.raise_for_status()

                media_data = resp.json()
                posts = parse_media(media_data)

        except Exception:
            pass

        return posts
