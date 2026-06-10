"""Facebook collector via Meta Graph API."""
from datetime import datetime
from typing import Any

import httpx

from app.core.config import settings
from app.social.base import BaseSocialCollector, SocialPostData


def parse_posts(data: dict[str, Any]) -> list[SocialPostData]:
    """Parse Facebook page posts from Graph API response.

    Args:
        data: JSON response dict from Graph API

    Returns:
        List of SocialPostData objects extracted from the response
    """
    posts: list[SocialPostData] = []

    for page in data.get("data", []):
        try:
            # Extract page name or message as content
            content = page.get("name", "") or page.get("message", "")
            if not content:
                continue

            post_url = page.get("link")
            updated_time = page.get("updated_time")

            posted_at: datetime | None = None
            if updated_time:
                try:
                    posted_at = datetime.fromisoformat(updated_time.replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            posts.append(
                SocialPostData(
                    platform="facebook",
                    post_url=post_url,
                    content=content,
                    posted_at=posted_at,
                )
            )
        except Exception:
            continue

    return posts


class FacebookCollector(BaseSocialCollector):
    """Collect posts from Facebook via Meta Graph API (limited)."""

    PLATFORM = "facebook"
    RATE_LIMIT_SEC = 1.0

    async def collect(self, query: str) -> list[SocialPostData]:
        """Collect Facebook page posts (minimal implementation)."""
        posts: list[SocialPostData] = []

        # Facebook public content search is restricted; return empty
        # unless instagram_access_token is available (shared Meta token)
        if not settings.instagram_access_token:
            return posts

        try:
            await self._wait_rate_limit()

            params = {
                "type": "page",
                "q": query,
                "access_token": settings.instagram_access_token,
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    "https://graph.facebook.com/v21.0/search",
                    params=params,
                )
                resp.raise_for_status()

            data = resp.json()
            posts = parse_posts(data)

        except Exception:
            pass

        return posts
