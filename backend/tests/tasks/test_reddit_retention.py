"""48시간 보존 강제 — Reddit 약관 준수의 핵심이라 실제 DB 경계로 검증한다.

약관: 삭제된 콘텐츠는 우리도 지워야 하고, 저장 데이터는 48시간 내 주기적 삭제 권고.
"익명화해도 보관은 위반"이므로 soft delete가 아니라 행 삭제여야 한다.
"""
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal, engine
from app.models.social_post import SocialPost
from app.scrapers.reddit_deals import now_utc
from app.tasks.reddit_signals import PLATFORM, RETENTION_HOURS, _purge

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _dispose_engine():
    """asyncpg 커넥션은 생성된 이벤트 루프에 묶인다 — 테스트마다 풀을 비운다."""
    yield
    await engine.dispose()


async def _insert(hours_ago: float, url: str, platform: str = PLATFORM) -> None:
    async with AsyncSessionLocal() as db:
        db.add(
            SocialPost(
                platform=platform,
                post_url=url,
                content="[Glossier] 10% off Glossier",
                created_at=now_utc() - timedelta(hours=hours_ago),
            )
        )
        await db.commit()


async def _count(url: str) -> int:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(func.count()).select_from(SocialPost).where(SocialPost.post_url == url)
        )
        return int(result.scalar() or 0)


async def _cleanup(*urls: str) -> None:
    async with AsyncSessionLocal() as db:
        for url in urls:
            for row in (await db.execute(select(SocialPost).where(SocialPost.post_url == url))).scalars():
                await db.delete(row)
        await db.commit()


async def test_retention_boundary_is_enforced() -> None:
    fresh = "https://reddit.test/fresh-47h"
    stale = "https://reddit.test/stale-49h"
    slickdeals_stale = "https://slickdeals.test/stale-49h"
    await _cleanup(fresh, stale, slickdeals_stale)
    await _insert(RETENTION_HOURS - 1, fresh)
    await _insert(RETENTION_HOURS + 1, stale)
    await _insert(RETENTION_HOURS + 1, slickdeals_stale, platform="slickdeals")

    try:
        assert await _count(fresh) == 1
        assert await _count(stale) == 1
        assert await _count(slickdeals_stale) == 1

        await _purge()

        # 48시간 이내는 남고, 넘긴 Reddit/Slickdeals 원문은 사라진다.
        assert await _count(fresh) == 1
        assert await _count(stale) == 0
        assert await _count(slickdeals_stale) == 0
    finally:
        await _cleanup(fresh, stale, slickdeals_stale)


async def test_retention_window_is_48_hours() -> None:
    """이 값을 늘리는 것은 정책 위반이다 — 상수를 못박는다."""
    assert RETENTION_HOURS == 48


async def test_purge_only_touches_reddit_and_slickdeals_rows() -> None:
    """다른 플랫폼의 보존 정책까지 이 태스크가 결정하면 안 된다."""
    other = "https://instagram.test/old-post"
    await _cleanup(other)
    async with AsyncSessionLocal() as db:
        db.add(
            SocialPost(
                platform="instagram",
                post_url=other,
                content="old",
                created_at=now_utc() - timedelta(hours=RETENTION_HOURS * 10),
            )
        )
        await db.commit()
    try:
        await _purge()
        assert await _count(other) == 1
    finally:
        await _cleanup(other)
