"""Naver Blog collector via Naver Search API."""
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.social.base import BaseSocialCollector, SocialPostData


def parse_response(data: dict[str, Any], platform: str) -> list[SocialPostData]:
    """Parse Naver Search API blog response.

    Args:
        data: JSON response dict from Naver Search API
        platform: Platform name string

    Returns:
        List of SocialPostData objects extracted from the response
    """
    posts: list[SocialPostData] = []
    for item in data.get("items", []):
        try:
            title = item.get("title", "")
            description = item.get("description", "")

            # Strip HTML tags (simple <b> tag removal)
            title_clean = title.replace("<b>", "").replace("</b>", "")
            description_clean = description.replace("<b>", "").replace("</b>", "")

            content = (title_clean + " " + description_clean).strip()
            if not content:
                continue

            post_url = item.get("link")
            postdate_str = item.get("postdate")

            # Parse postdate as YYYYMMDD format defensively
            posted_at: datetime | None = None
            if postdate_str and len(str(postdate_str)) == 8:
                try:
                    posted_at = datetime.strptime(str(postdate_str), "%Y%m%d")
                except (ValueError, TypeError):
                    pass

            posts.append(
                SocialPostData(
                    platform=platform,
                    post_url=post_url,
                    content=content,
                    posted_at=posted_at,
                )
            )
        except Exception:
            continue

    return posts


class NaverBlogCollector(BaseSocialCollector):
    """Collect posts from Naver Blog via Naver Search API."""

    PLATFORM = "naver_blog"
    RATE_LIMIT_SEC = 1.0

    async def collect(self, query: str) -> list[SocialPostData]:
        """Collect blog posts mentioning the product."""
        posts: list[SocialPostData] = []

        if not settings.naver_client_id or not settings.naver_client_secret:
            return posts

        try:
            await self._wait_rate_limit()
            headers = {
                "X-Naver-Client-Id": settings.naver_client_id,
                "X-Naver-Client-Secret": settings.naver_client_secret,
            }
            params: dict[str, str | int] = {
                "query": query,
                "display": 20,
                "sort": "date",
            }
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://openapi.naver.com/v1/search/blog.json",
                    headers=headers,
                    params=params,
                )
                resp.raise_for_status()

            data = resp.json()
            posts = parse_response(data, self.PLATFORM)
        except Exception:
            pass

        return posts
