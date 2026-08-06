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


@pytest.mark.asyncio
async def test_prediction_survives_a_single_outlier_year() -> None:
    """실측: 블프 11년치 중 10년이 W47~48인데 W28짜리 하울 하나로 편차가 20이 됐다.
    최대-최소로 판정하면 그 하나에 무너지므로 중앙값 ±1주 집중도를 쓴다."""
    async with AsyncSessionLocal() as db:
        weeks = [47, 47, 47, 48, 48, 48, 47, 48, 28]  # 마지막이 이상치
        for i, week in enumerate(weeks):
            await sale_windows.record(db, sale_windows.Observation(
                brand="TEST_BF", source="youtube_timing",
                on=sale_windows.monday_of(2010 + i, week),
                is_estimate=True, recurrence_key="TEST_bf",
                source_url=f"ytsearch:TEST_bf:{2010 + i}",
            ))
        await db.commit()

        pred = await sale_windows.predict(db, "TEST_bf")
        assert pred is not None
        assert pred.iso_week in (47, 48)
        assert pred.week_spread >= 19          # 이상치가 편차는 망가뜨리지만
        assert pred.concentration >= 0.85      # 집중도는 견딘다
        assert pred.is_reliable


@pytest.mark.asyncio
async def test_moving_event_is_not_declared_reliable() -> None:
    """프라임데이는 해마다 움직인다 — 집중도가 낮으면 주차를 단정하지 않는다."""
    async with AsyncSessionLocal() as db:
        for i, week in enumerate([25, 27, 27, 2, 28, 26]):
            await sale_windows.record(db, sale_windows.Observation(
                brand="TEST_PD", source="youtube_timing",
                on=sale_windows.monday_of(2019 + i, week),
                is_estimate=True, recurrence_key="TEST_pd",
                source_url=f"ytsearch:TEST_pd:{2019 + i}",
            ))
        await db.commit()
        pred = await sale_windows.predict(db, "TEST_pd")
        assert pred is not None and not pred.is_reliable


@pytest.mark.asyncio
async def test_two_years_is_not_enough() -> None:
    async with AsyncSessionLocal() as db:
        for i in range(2):
            await sale_windows.record(db, sale_windows.Observation(
                brand="TEST_Thin", source="youtube_timing",
                on=sale_windows.monday_of(2024 + i, 15),
                is_estimate=True, recurrence_key="TEST_thin",
                source_url=f"ytsearch:TEST_thin:{2024 + i}",
            ))
        await db.commit()
        pred = await sale_windows.predict(db, "TEST_thin")
        assert pred is not None
        assert pred.concentration == 1.0      # 완벽히 일치해도
        assert not pred.is_reliable           # 2년으로는 반복이라 못 한다
