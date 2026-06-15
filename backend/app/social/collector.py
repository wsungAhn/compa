"""Orchestrate social media collectors and store posts in database."""
from collections.abc import Callable
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.social_post import SocialPost
from app.social.base import BaseSocialCollector
from app.social.facebook import FacebookCollector
from app.social.instagram import InstagramCollector
from app.social.naver_blog import NaverBlogCollector
from app.social.tiktok import TikTokCollector

# Registry of collectors
COLLECTORS: dict[str, Callable[[], BaseSocialCollector]] = {
    "naver_blog": NaverBlogCollector,
    "instagram": InstagramCollector,
    "tiktok": TikTokCollector,
    "facebook": FacebookCollector,
}


async def collect_social_posts(db: AsyncSession, query: str) -> int:
    """Collect social posts from all platforms and store new ones in database.

    Args:
        db: AsyncSession database connection
        query: Product name/query to search for

    Returns:
        Number of new posts inserted
    """
    all_posts: list[dict[str, Any]] = []

    # Run each collector (continue on failure)
    for platform_name, collector_class in COLLECTORS.items():
        try:
            collector = collector_class()
            posts = await collector.collect(query)

            for post in posts:
                all_posts.append(
                    {
                        "platform": post.platform,
                        "post_url": post.post_url,
                        "content": post.content,
                        "posted_at": post.posted_at,
                        "processed": False,
                    }
                )
        except Exception:
            # Continue on any collector failure
            continue

    if not all_posts:
        return 0

    # Deduplicate by post_url against existing SocialPost rows
    post_urls = [p["post_url"] for p in all_posts if p["post_url"]]
    if post_urls:
        result = await db.execute(
            select(SocialPost.post_url).where(SocialPost.post_url.in_(post_urls))
        )
        existing_urls = set(result.scalars().all())

        # Filter out duplicates
        all_posts = [p for p in all_posts if p["post_url"] not in existing_urls]

    if not all_posts:
        return 0

    # Insert new posts
    await db.execute(insert(SocialPost).values(all_posts))
    await db.commit()

    return len(all_posts)
