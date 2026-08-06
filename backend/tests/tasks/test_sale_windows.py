"""세일 창 슬롯 — 모든 소스가 같은 자리에 쌓이는지, 파생 정보가 정확한지."""
from datetime import date

import pytest
from sqlalchemy import delete, select

from app.core import sale_windows
from app.core.database import AsyncSessionLocal, engine
from app.models.sale_window import SaleWindow

# 동기 순수함수 테스트가 섞여 있어 모듈 전역 asyncio 마크를 쓰지 않는다


@pytest.fixture(autouse=True)
async def _clean():
    yield
    async with AsyncSessionLocal() as db:
        await db.execute(delete(SaleWindow).where(SaleWindow.brand.like("TEST_%")))
        await db.commit()
    await engine.dispose()


def test_scope_reads_sitewide_from_the_title() -> None:
    """같은 25%라도 사이트와이드와 단일 품목은 값어치가 다르다."""
    assert sale_windows.classify_scope("25% Off Sitewide: Kiehl's Sale") == "sitewide"
    assert sale_windows.classify_scope("Torriden Serum Set $14.9") == "item"
    assert sale_windows.classify_scope("") == "unknown"


def test_discount_is_parsed_only_when_sane() -> None:
    assert sale_windows.parse_discount_pct("25% off everything") == 25.0
    assert sale_windows.parse_discount_pct("extra 15% with code") == 15.0
    assert sale_windows.parse_discount_pct("no discount mentioned") is None
    assert sale_windows.parse_discount_pct("100% off scam") is None


def test_iso_week_handles_year_boundary() -> None:
    """연말은 달력 연도와 ISO 연도가 갈린다 — 여기서 틀리면 슬롯이 어긋난다."""
    assert sale_windows.week_of(date(2027, 1, 1)) == (2026, 53)
    assert sale_windows.week_of(date(2026, 11, 27))[1] == 48


@pytest.mark.asyncio
async def test_record_writes_a_slot() -> None:
    async with AsyncSessionLocal() as db:
        await sale_windows.record(db, sale_windows.Observation(
            brand="TEST_Kiehls", source="slickdeals", on=date(2026, 8, 6),
            event_name="25% Off Sitewide", discount_pct=25.0, retailer="Kiehl's",
            country="US", source_url="https://slickdeals.test/1", scope="sitewide",
        ))
        await db.commit()
        row = (await db.execute(select(SaleWindow).where(SaleWindow.brand == "TEST_Kiehls"))).scalar_one()
        assert (row.iso_year, row.iso_week) == (2026, 32)
        assert row.observed_on == date(2026, 8, 6)
        assert row.scope == "sitewide"
        assert row.verified is False   # 소셜 신호는 검증 전까지 승격하지 않는다


@pytest.mark.asyncio
async def test_same_source_url_is_not_recorded_twice() -> None:
    obs = sale_windows.Observation(
        brand="TEST_Dup", source="reddit", on=date(2026, 8, 6),
        source_url="https://reddit.test/dup",
    )
    async with AsyncSessionLocal() as db:
        assert await sale_windows.record(db, obs) is not None
        await db.commit()
    async with AsyncSessionLocal() as db:
        assert await sale_windows.record(db, obs) is None   # 주기 실행 시 중복 방지
        await db.commit()


@pytest.mark.asyncio
async def test_estimates_do_not_claim_an_exact_date() -> None:
    """YouTube 분포는 '그 주에 몰렸다'이지 '그날이었다'가 아니다."""
    async with AsyncSessionLocal() as db:
        await sale_windows.record(db, sale_windows.Observation(
            brand="TEST_Sephora", source="youtube_timing", on=date(2026, 4, 8),
            is_estimate=True, sample_size=60, corroborations=2,
            recurrence_key="sephora_spring", source_url=None,
        ))
        await db.commit()
        row = (await db.execute(select(SaleWindow).where(SaleWindow.brand == "TEST_Sephora"))).scalar_one()
        assert row.observed_on is None       # 날짜를 아는 척하지 않는다
        assert row.iso_week == 15            # 슬롯은 남는다
        assert row.is_estimate is True
        assert row.recurrence_key == "sephora_spring"
