"""TikTok collector via TikTok Research API."""
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.social.base import BaseSocialCollector, SocialPostData


def parse_response(data: dict[str, Any]) -> list[SocialPostData]:
    """Parse TikTok Research API response.

    Args:
        data: JSON response dict from TikTok Research API

    Returns:
        List of SocialPostData objects extracted from the response
    """
    posts: list[SocialPostData] = []

    for video in data.get("data", {}).get("videos", []):
        try:
            description = video.get("video_description", "")
            if not description:
                continue

            # Build share URL from video ID or use provided share_url
            share_url = video.get("share_url")
            video_id = video.get("id")
            if not share_url and video_id:
                share_url = f"https://www.tiktok.com/@unknown/video/{video_id}"

            # Parse create_time as epoch timestamp
            posted_at: datetime | None = None
            create_time = video.get("create_time")
            if create_time:
                try:
                    posted_at = datetime.fromtimestamp(int(create_time))
                except (ValueError, TypeError, OSError):
                    pass

            posts.append(
                SocialPostData(
                    platform="tiktok",
                    post_url=share_url,
                    content=description,
                    posted_at=posted_at,
                )
            )
        except Exception:
            continue

    return posts


class TikTokCollector(BaseSocialCollector):
    """Collect posts from TikTok via TikTok Research API."""

    PLATFORM = "tiktok"
    RATE_LIMIT_SEC = 1.0

    async def collect(self, query: str) -> list[SocialPostData]:
        """Collect TikTok videos via Research API."""
        posts: list[SocialPostData] = []

        if not settings.tiktok_client_key:
            return posts

        try:
            await self._wait_rate_limit()

            headers = {
                "Authorization": f"Bearer {settings.tiktok_client_key}",
                "Content-Type": "application/json",
            }

            body = {
                "query": {
                    "and": [
                        {
                            "operation": "IN",
                            "field_name": "keyword",
                            "field_values": [query],
                        }
                    ]
                },
                "max_count": 20,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://open.tiktokapis.com/v2/research/video/query/",
                    json=body,
                    headers=headers,
                )
                resp.raise_for_status()

            data = resp.json()
            posts = parse_response(data)

        except Exception:
            pass

        return posts
