"""async DB 엔진의 이벤트 루프 경계 회귀 테스트."""
import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from app.core.database import AsyncSessionLocal, engine
from app.models.product import Product
from app.scrapers.collector import _BROWSER_SCRAPERS, get_enabled_scrapers
from app.tasks.classify import classify_pending

SESSION_RUN_COUNT = 3
CLASSIFY_RUN_COUNT = 2
BROWSER_SCRAPER_LIMIT = 5


async def _query_product_once() -> None:
    async with AsyncSessionLocal() as db:
        await db.execute(select(Product).limit(1))
        await db.commit()


def _run_product_query() -> None:
    asyncio.run(_query_product_once())


async def _probe_live_pg_query() -> None:
    try:
        await _query_product_once()
    finally:
        await engine.dispose()


def _live_pg_skip_reason() -> str | None:
    try:
        asyncio.run(_probe_live_pg_query())
    except (OSError, SQLAlchemyError) as exc:
        return f"requires live PG: {type(exc).__name__}: {exc}"
    return None


LIVE_PG_SKIP_REASON = _live_pg_skip_reason()
LIVE_PG_UNAVAILABLE = LIVE_PG_SKIP_REASON is not None
LIVE_PG_MARK_REASON = LIVE_PG_SKIP_REASON or "requires live PG"


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
def test_async_session_survives_repeated_asyncio_run() -> None:
    for _ in range(SESSION_RUN_COUNT):
        _run_product_query()


def test_async_engine_uses_null_pool() -> None:
    assert isinstance(engine.pool, NullPool)


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
def test_classify_pending_survives_repeated_sync_wrapper_calls() -> None:
    for _ in range(CLASSIFY_RUN_COUNT):
        assert classify_pending(limit=0) == 0


def test_browser_scraper_tripwire_stays_below_loop_bound_threshold() -> None:
    enabled_browser_scrapers = set(get_enabled_scrapers()) & set(_BROWSER_SCRAPERS)

    assert len(enabled_browser_scrapers) < BROWSER_SCRAPER_LIMIT
