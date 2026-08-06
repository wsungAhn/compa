"""Reddit 딜 신호 수집 + 48시간 보존 강제.

Reddit 약관은 삭제된 콘텐츠를 우리도 지우도록 요구하고, 저장 데이터를 48시간 내에
주기적으로 삭제할 것을 강하게 권고한다 — **익명화해도 보관은 위반**이다.
"기억해서 지운다"는 통제가 아니므로 정리를 태스크로 박고 beat에 매시간 등록한다.
"""
import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, select

from app.core import sale_windows
from app.core.database import AsyncSessionLocal
from app.models.social_post import SocialPost
from app.scrapers.brands.shopify import BRANDS
from app.scrapers import slickdeals
from app.scrapers.reddit_deals import fetch_all_subreddits, now_utc
from app.tasks import celery

logger = logging.getLogger(__name__)

PLATFORM = "reddit"
# 약관 권고치. 이 값을 늘리는 것은 정책 위반이므로 상수로 고정한다.
RETENTION_HOURS = 48


def collect_reddit_signals() -> int:
    """딜 신호를 수집해 social_posts에 남긴다(가격으로 승격하지 않는다)."""
    return asyncio.run(_collect())


async def _collect() -> int:
    brands = [brand for _name, _domain, brand in BRANDS]
    signals = await fetch_all_subreddits(brands)
    if not signals:
        return 0

    stored = 0
    async with AsyncSessionLocal() as db:
        for signal in signals:
            # 두 테이블은 수명이 다르다 — 원문(social_posts)은 48시간 뒤 지워지고
            # 슬롯(sale_windows)은 남는다. 중복 판정도 각자 해야 이력이 안 비어버린다.
            duplicate_post = False
            if signal.url:
                existing = await db.execute(
                    select(SocialPost).where(SocialPost.post_url == signal.url)
                )
                duplicate_post = existing.scalar_one_or_none() is not None

            if not duplicate_post:
                db.add(
                    SocialPost(
                        platform=PLATFORM,
                        post_url=signal.url or None,
                        content=f"[{signal.brand}] {signal.title}",
                        posted_at=signal.posted_at,
                        # 신호이지 사실이 아니다 — 공홈 실가격이 확인해줄 때만 승격한다.
                        sale_event_id=None,
                    )
                )

            recorded = None
            if signal.posted_at:
                recorded = await sale_windows.record(
                    db,
                    sale_windows.Observation(
                        brand=signal.brand,
                        source="reddit",
                        on=signal.posted_at.date(),
                        event_name=signal.title[:255],
                        discount_pct=sale_windows.parse_discount_pct(signal.title),
                        country="US",
                        source_url=signal.url or None,
                        scope=sale_windows.classify_scope(signal.title),
                    ),
                )
            if not duplicate_post or recorded is not None:
                stored += 1
        await db.commit()
    logger.info("reddit: %d signals stored (%d fetched)", stored, len(signals))
    return stored


def collect_slickdeals_signals() -> int:
    """Slickdeals 딜 신호. Reddit과 나란히 두는 추가 소스 — 소스는 누적이다."""
    return asyncio.run(_collect_slickdeals())


async def _collect_slickdeals() -> int:
    signals = await slickdeals.fetch_all()
    if not signals:
        return 0
    stored = 0
    async with AsyncSessionLocal() as db:
        for signal in signals:
            # 두 테이블은 수명이 다르다 — 원문(social_posts)은 휘발성이고 슬롯
            # (sale_windows)은 영구다. 그래서 중복 판정도 각자 한다. 원문이 이미
            # 있다고 슬롯 기록까지 건너뛰면 이력이 비어버린다.
            duplicate_post = False
            if signal.url:
                existing = await db.execute(
                    select(SocialPost).where(SocialPost.post_url == signal.url)
                )
                duplicate_post = existing.scalar_one_or_none() is not None
            price = f" (${signal.price:,.2f})" if signal.price else ""
            if not duplicate_post:
                db.add(
                    SocialPost(
                        platform="slickdeals",
                        post_url=signal.url or None,
                        content=f"[{signal.brand}] {signal.title}{price}",
                        posted_at=signal.posted_at,
                        sale_event_id=None,
                    )
                )
            # 원문은 휘발성이지만 슬롯 기록은 남는다 — 이력은 여기서 쌓인다.
            recorded = await sale_windows.record(
                db,
                sale_windows.Observation(
                    brand=signal.brand,
                    source="slickdeals",
                    on=signal.posted_at.date(),
                    event_name=signal.title[:255],
                    discount_pct=sale_windows.parse_discount_pct(signal.title),
                    price=signal.price,
                    currency="USD",
                    country="US",
                    source_url=signal.url or None,
                    scope=sale_windows.classify_scope(signal.title),
                ),
            )
            if not duplicate_post or recorded is not None:
                stored += 1
        await db.commit()
    logger.info("slickdeals: %d signals stored (%d fetched)", stored, len(signals))
    return stored


def purge_expired_social_posts() -> int:
    """48시간이 지난 reddit 행을 하드 삭제한다.

    soft delete가 아니다 — 보관 자체가 약관 위반이므로 행을 지운다. 승격된 신호도
    예외가 아니다: sale_events에 남는 값은 우리가 공홈에서 독립 관측한 가격이지
    Reddit 사용자 콘텐츠가 아니므로, 원문을 지워도 가격 데이터는 유지된다.
    """
    return asyncio.run(_purge())


async def _purge() -> int:
    cutoff = now_utc() - timedelta(hours=RETENTION_HOURS)
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(SocialPost).where(
                SocialPost.platform == PLATFORM,
                SocialPost.created_at < cutoff,
            )
        )
        await db.commit()
    deleted = int(result.rowcount or 0)
    if deleted:
        logger.info("reddit: purged %d posts older than %dh", deleted, RETENTION_HOURS)
    return deleted


collect_reddit_signals = celery.task(collect_reddit_signals)
collect_slickdeals_signals = celery.task(collect_slickdeals_signals)
purge_expired_social_posts = celery.task(purge_expired_social_posts)
