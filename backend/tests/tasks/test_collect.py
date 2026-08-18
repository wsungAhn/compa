"""일일 브랜드 스윕 계약 테스트."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any, Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from app.ai import matcher
from app.core.database import AsyncSessionLocal, engine
from app.models.platform import Platform
from app.models.platform_product_id import PlatformProductId
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.scrapers import collector
from app.scrapers.base import ScrapedEvent
from app.scrapers.brands import shopify
from app.tasks import collect


class _ScalarRows:
    def __init__(self, rows: Sequence[object]) -> None:
        self._rows = list(rows)

    def all(self) -> list[object]:
        return list(self._rows)


class _QueryResult:
    def __init__(
        self,
        *,
        scalar_value: object | None = None,
        rows: Sequence[object] | None = None,
    ) -> None:
        self._scalar_value = scalar_value
        self._rows = list(rows or [])

    def scalar_one_or_none(self) -> object | None:
        return self._scalar_value

    def first(self) -> object | None:
        if not self._rows:
            return None
        return self._rows[0]

    def scalars(self) -> _ScalarRows:
        return _ScalarRows(self._rows)


class _SweepDb:
    def __init__(self) -> None:
        self.rollback_calls = 0

    async def rollback(self) -> None:
        self.rollback_calls += 1


class _SweepSessionContext:
    def __init__(self, db: _SweepDb) -> None:
        self._db = db

    async def __aenter__(self) -> _SweepDb:
        return self._db

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False


class _PersistSession:
    def __init__(self, inserted_rows: int = 1) -> None:
        self.executed: list[object] = []
        self.commits = 0
        self.inserted_rows = inserted_rows

    async def execute(self, statement: object) -> _QueryResult:
        self.executed.append(statement)
        return _QueryResult(rows=[uuid.uuid4() for _ in range(self.inserted_rows)])

    async def commit(self) -> None:
        self.commits += 1


class _HelperSession:
    def __init__(self, rows: Sequence[Product]) -> None:
        self.rows = list(rows)
        self.executed: list[object] = []

    async def execute(self, statement: object) -> _QueryResult:
        self.executed.append(statement)
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
        if "FROM products" not in compiled:
            raise AssertionError(f"unexpected execute: {compiled}")
        return _QueryResult(rows=self.rows)

    async def rollback(self) -> None:
        return None


class _CollectPlatformSession:
    def __init__(self, product: Product) -> None:
        self.product = product
        self.executed: list[object] = []

    async def execute(self, statement: object) -> _QueryResult:
        self.executed.append(statement)
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
        if "FROM products" in compiled:
            return _QueryResult(scalar_value=self.product)
        raise AssertionError(f"unexpected execute: {compiled}")

    async def rollback(self) -> None:
        return None


def _make_brand_scraper(platform_name: str, brand: str, events: list[ScrapedEvent], calls: list[str]) -> type[object]:
    class _Scraper:
        BRAND = brand
        PLATFORM_NAME = platform_name

        async def scrape(self, query: str) -> list[ScrapedEvent]:
            calls.append(query)
            return events

    return _Scraper


def _patch_sweep_runtime(
    monkeypatch: pytest.MonkeyPatch,
    *,
    brand_scrapers: dict[str, type[object]],
    enabled_scrapers: dict[str, object] | None = None,
    db: _SweepDb | None = None,
) -> _SweepDb:
    sweep_db = db or _SweepDb()
    monkeypatch.setattr(collect, "AsyncSessionLocal", lambda: _SweepSessionContext(sweep_db))
    monkeypatch.setattr(collect, "BRAND_SCRAPERS", brand_scrapers)
    monkeypatch.setattr(
        collect,
        "get_enabled_scrapers",
        lambda: enabled_scrapers if enabled_scrapers is not None else {name: object() for name in brand_scrapers},
    )
    return sweep_db


async def _probe_live_pg_query() -> None:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(select(Product).limit(1))
            await db.commit()
    finally:
        await engine.dispose()


def _live_pg_skip_reason() -> str | None:
    try:
        import asyncio

        asyncio.run(_probe_live_pg_query())
    except (OSError, SQLAlchemyError) as exc:
        return f"requires live PG: {type(exc).__name__}: {exc}"
    return None


LIVE_PG_SKIP_REASON = _live_pg_skip_reason()
LIVE_PG_UNAVAILABLE = LIVE_PG_SKIP_REASON is not None
LIVE_PG_MARK_REASON = LIVE_PG_SKIP_REASON or "requires live PG"


@pytest.mark.asyncio
async def test_t1_name_kr_none_product_is_included(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", name_kr=None, brand="Tatcha")
    miss_product = Product(id=uuid.uuid4(), name_en="Not In Catalog", name_kr=None, brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    events = [
        ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0),
        ScrapedEvent(product_name="Other Cream", brand="Tatcha", sale_price=70.0),
    ]
    calls: list[str] = []
    sweep_db = _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={"Tatcha 공홈": _make_brand_scraper("Tatcha 공홈", "Tatcha", events, calls)},
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(
        matcher,
        "find_matching_product",
        AsyncMock(side_effect=AssertionError("Claude path must not run")),
    )
    monkeypatch.setattr(
        matcher,
        "_ask_claude_for_match",
        AsyncMock(side_effect=AssertionError("Claude path must not run")),
    )
    session = _HelperSession([product, miss_product])
    monkeypatch.setattr(collect, "AsyncSessionLocal", lambda: _SweepSessionContext(session))
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock(return_value=(1, set())))

    result = await collect._collect_all()

    assert result == 1
    assert calls == [""]
    assert sweep_db.rollback_calls == 0


@pytest.mark.asyncio
async def test_t2_brand_scrape_called_once_per_brand(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    brand_scrapers = {
        "Tatcha 공홈": _make_brand_scraper(
            "Tatcha 공홈",
            "Tatcha",
            [ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0)],
            calls,
        ),
        "SK-II 공홈": _make_brand_scraper(
            "SK-II 공홈",
            "SK-II",
            [ScrapedEvent(product_name="Facial Treatment Essence", brand="SK-II", sale_price=150.0)],
            calls,
        ),
    }
    _patch_sweep_runtime(monkeypatch, brand_scrapers=brand_scrapers)
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock(return_value=product))
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock(return_value=(1, set())))

    result = await collect._collect_all()

    assert result == 2
    assert calls == ["", ""]


@pytest.mark.asyncio
async def test_t3_unmatched_catalog_product_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
            "Tatcha 공홈": _make_brand_scraper(
                "Tatcha 공홈",
                "Tatcha",
                [ScrapedEvent(product_name="New Product", brand="Tatcha", sale_price=70.0)],
                calls,
            ),
        },
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock(return_value=None))
    persist = AsyncMock(return_value=(1, set()))
    monkeypatch.setattr(collect, "persist_events_for_product", persist)

    result = await collect._collect_all()

    assert result == 0
    persist.assert_not_awaited()


@pytest.mark.asyncio
async def test_t4_db_error_rolls_back_and_next_brand_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    sweep_db = _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
            "Tatcha 공홈": _make_brand_scraper(
                "Tatcha 공홈",
                "Tatcha",
                [ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0)],
                calls,
            ),
            "SK-II 공홈": _make_brand_scraper(
                "SK-II 공홈",
                "SK-II",
                [ScrapedEvent(product_name="Facial Treatment Essence", brand="SK-II", sale_price=150.0)],
                calls,
            ),
        },
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock(return_value=product))
    persist = AsyncMock(side_effect=[RuntimeError("boom"), (1, set())])
    monkeypatch.setattr(collect, "persist_events_for_product", persist)

    result = await collect._collect_all()

    assert result == 1
    assert sweep_db.rollback_calls == 1
    assert persist.await_count == 2


@pytest.mark.asyncio
async def test_t5_sentinel_only_brand_counts_as_fail(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    caplog.set_level(logging.WARNING)
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
            "Tatcha 공홈": _make_brand_scraper(
                "Tatcha 공홈",
                "Tatcha",
                [ScrapedEvent(product_name="blocked", confidence=0.0, raw_text="blocked")],
                [],
            ),
        },
    )
    get_platform = AsyncMock(return_value=platform)
    monkeypatch.setattr(collect, "get_platform", get_platform)
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock())
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock())

    result = await collect._collect_all()

    assert result == 0
    get_platform.assert_not_awaited()
    assert any("scrape failed" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_t5b_empty_positive_events_counts_as_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
            "Tatcha 공홈": _make_brand_scraper("Tatcha 공홈", "Tatcha", [], []),
        },
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock())
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock())

    result = await collect._collect_all()

    assert result == 0


def test_t6_nameless_events_are_grouped_out() -> None:
    grouped = collector.group_events_by_product_name(
        [
            ScrapedEvent(product_name=""),
            ScrapedEvent(product_name="   "),
            ScrapedEvent(product_name=" The Water Cream "),
        ]
    )

    assert grouped == {"The Water Cream": [ScrapedEvent(product_name=" The Water Cream ")]}


def test_scraped_event_accepts_external_identifier_fields() -> None:
    event = ScrapedEvent(product_name="The Water Cream", external_id="40111", id_type="variant_id")

    assert event.external_id == "40111"
    assert event.id_type == "variant_id"


@pytest.mark.asyncio
async def test_t7_same_brand_different_name_is_not_matched(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _HelperSession(
        [Product(id=uuid.uuid4(), name_en="Other Cream", brand="Tatcha")]
    )

    result = await collector.find_exact_for_sweep(session, "The Water Cream", "Tatcha")

    assert result is None


@pytest.mark.asyncio
async def test_t8_sweep_path_never_calls_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    miss_product = Product(id=uuid.uuid4(), name_en="Not In Catalog", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    session = _HelperSession([product, miss_product])
    calls: list[str] = []
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
                "Tatcha 공홈": _make_brand_scraper(
                    "Tatcha 공홈",
                    "Tatcha",
                    [
                        ScrapedEvent(product_name="Other Cream", brand="Tatcha", sale_price=55.0),
                        ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0),
                    ],
                    calls,
                ),
            },
        )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(
        matcher,
        "find_matching_product",
        AsyncMock(side_effect=AssertionError("Claude path must not run")),
    )
    monkeypatch.setattr(
        matcher,
        "_ask_claude_for_match",
        AsyncMock(side_effect=AssertionError("Claude path must not run")),
    )
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock(return_value=(1, set())))
    monkeypatch.setattr(collect, "AsyncSessionLocal", lambda: _SweepSessionContext(session))

    result = await collect._collect_all()

    assert result == 1
    assert calls == [""]


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
@pytest.mark.asyncio
async def test_t9_live_pg_duplicate_insert_returns_zero_on_second_run() -> None:
    marker = f"brand-sweep-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        product = Product(name_en=marker, brand="Test Brand")
        platform = Platform(name=marker, country="US")
        db.add(product)
        db.add(platform)
        await db.commit()
        await db.refresh(product)
        await db.refresh(platform)

        event = ScrapedEvent(
            product_name=marker,
            brand="Test Brand",
            original_price=20.0,
            sale_price=10.0,
            currency="USD",
            start_date=date(2026, 8, 8),
            source_url="https://example.com/product",
            confidence=0.95,
            size_ml=50.0,
        )

        first, first_used_product_ids = await collector.persist_events_for_product(db, product, platform, [event])
        second, second_used_product_ids = await collector.persist_events_for_product(db, product, platform, [event])

        assert first == 1
        assert second == 0
        assert first_used_product_ids == {product.id}
        assert second_used_product_ids == {product.id}

        await db.execute(delete(SaleEvent).where(SaleEvent.product_id == product.id))
        await db.execute(delete(Product).where(Product.id == product.id))
        await db.execute(delete(Platform).where(Platform.id == platform.id))
        await db.commit()


@pytest.mark.asyncio
async def test_t10_persist_events_preserves_storage_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _PersistSession(inserted_rows=1)
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    event = ScrapedEvent(
        product_name="The Water Cream",
        brand="Tatcha",
        original_price=20.0,
        sale_price=10.0,
        discount_rate=50.0,
        currency=None,
        start_date=date(2026, 8, 8),
        source_url="https://example.com/product",
        confidence=0.69,
        raw_text="raw text",
        size_ml=50.0,
    )
    monkeypatch.setattr(collector, "_classify_event_type", lambda s: "surprise")
    monkeypatch.setattr(collector, "_is_bundle", lambda name: True)
    monkeypatch.setattr(collector, "safe_url", lambda url: "https://safe.example/product")

    inserted, used_product_ids = await collector.persist_events_for_product(session, product, platform, [event, ScrapedEvent(product_name="skip", confidence=0.0)])

    assert inserted == 1
    assert used_product_ids == {product.id}
    assert session.commits == 1
    compiled = str(session.executed[0].compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
    assert "surprise" in compiled
    assert "https://safe.example/product" in compiled
    assert "needs_review" in compiled and "true" in compiled.lower()
    assert "50.0" in compiled
    assert "raw text" in compiled
    assert "KRW" in compiled


@pytest.mark.asyncio
async def test_persist_events_uses_authoritative_external_id_product(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = _PersistSession(inserted_rows=1)
    source_product = Product(id=uuid.uuid4(), name_en="Renamed Cream", brand="Tatcha")
    mapped_product_id = uuid.uuid4()
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    event = ScrapedEvent(
        product_name="Renamed Cream",
        sale_price=70.0,
        external_id="40111",
        id_type="variant_id",
    )
    monkeypatch.setattr(collector, "upsert_platform_product_id", AsyncMock(return_value=mapped_product_id))
    caplog.set_level(logging.WARNING)

    inserted, used_product_ids = await collector.persist_events_for_product(session, source_product, platform, [event])

    assert inserted == 1
    assert used_product_ids == {mapped_product_id}
    compiled = str(session.executed[0].compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
    assert str(mapped_product_id) in compiled
    assert str(source_product.id) not in compiled
    assert any("external_id remapped sale event" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_t11_collect_all_does_not_call_search_path(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
            "Tatcha 공홈": _make_brand_scraper(
                "Tatcha 공홈",
                "Tatcha",
                [ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0)],
                calls,
            ),
        },
        enabled_scrapers={
            "Tatcha 공홈": object(),
            "Sephora": object(),
            "Amazon US": object(),
            "Rakuten": object(),
        },
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock(return_value=product))
    monkeypatch.setattr(collect, "collect_on_demand", AsyncMock(side_effect=AssertionError("search path must not run")))
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock(return_value=(1, set())))

    result = await collect._collect_all()

    assert result == 1
    assert calls == [""]


@pytest.mark.asyncio
async def test_t12_shopify_exact_250_products_warns(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "products": [
                    {
                        "title": f"Product {index}",
                        "product_type": "Serum",
                        "handle": f"product-{index}",
                        "variants": [{"price": "10.00", "compare_at_price": "20.00", "title": "50ml"}],
                    }
                    for index in range(250)
                ]
            }

    class _Client:
        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
            return False

        async def get(self, url: str, headers: dict[str, str]) -> _Response:
            return _Response()

    class _Scraper(shopify.ShopifyBrandScraper):
        PLATFORM_NAME = "Test Shopify"
        BRAND = "Test Brand"
        DOMAIN = "test.example"

    caplog.set_level(logging.WARNING)
    monkeypatch.setattr(shopify.httpx, "AsyncClient", lambda **kwargs: _Client())
    monkeypatch.setattr(_Scraper, "_wait_rate_limit", AsyncMock())

    events = await _Scraper().scrape("")

    assert len(events) == 250
    assert any("exactly 250 products" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_t13_missing_platform_counts_as_fail(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    calls: list[str] = []
    caplog.set_level(logging.WARNING)
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={
            "Tatcha 공홈": _make_brand_scraper(
                "Tatcha 공홈",
                "Tatcha",
                [ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0)],
                calls,
            ),
        },
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=None))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock(return_value=product))
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock(return_value=(1, set())))

    result = await collect._collect_all()

    assert result == 0
    assert any("missing platform row" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_t14_ambiguous_exact_match_is_skipped(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    candidate_one = Product(id=uuid.uuid4(), name_en="The  Water <b>Cream</b>", brand="Tatcha")
    candidate_two = Product(id=uuid.uuid4(), name_en="the water cream", brand="Tatcha")
    session = _HelperSession([candidate_one, candidate_two])
    caplog.set_level(logging.WARNING)

    result = await collector.find_exact_for_sweep(session, "The Water Cream", "Tatcha")

    assert result is None
    assert any("ambiguous" in record.message for record in caplog.records)


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
@pytest.mark.asyncio
async def test_t15_live_pg_size_variants_both_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    marker = f"brand-sweep-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        product = Product(name_en=marker, brand="Test Brand")
        platform = Platform(name=marker, country="US")
        db.add(product)
        db.add(platform)
        await db.commit()
        await db.refresh(product)
        await db.refresh(platform)

        base_kwargs = {
            "product_name": marker,
            "brand": "Test Brand",
            "original_price": 20.0,
            "sale_price": 10.0,
            "currency": "USD",
            "start_date": date(2026, 8, 8),
            "source_url": "https://example.com/product",
            "confidence": 0.95,
        }
        first = ScrapedEvent(**base_kwargs, size_ml=30.0)
        second = ScrapedEvent(**base_kwargs, size_ml=50.0)

        inserted, used_product_ids = await collector.persist_events_for_product(db, product, platform, [first, second])

        assert inserted == 2
        assert used_product_ids == {product.id}

        await db.execute(delete(SaleEvent).where(SaleEvent.product_id == product.id))
        await db.execute(delete(Product).where(Product.id == product.id))
        await db.execute(delete(Platform).where(Platform.id == platform.id))
        await db.commit()


@pytest.mark.asyncio
async def test_t16_no_enabled_brands_errors_and_returns_zero(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    monkeypatch.setattr(collect, "get_enabled_scrapers", lambda: {})
    monkeypatch.setattr(collect, "BRAND_SCRAPERS", {})
    monkeypatch.setattr(collect, "AsyncSessionLocal", MagicMock(side_effect=AssertionError("db must not open")))

    result = await collect._collect_all()

    assert result == 0
    assert any("no brand scrapers enabled" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_t17_collect_platform_returns_product_even_when_inserted_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    session = _CollectPlatformSession(product)
    monkeypatch.setattr(collector, "AsyncSessionLocal", lambda: _SweepSessionContext(session))
    monkeypatch.setattr(collector, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collector, "_fresh_platforms", AsyncMock(return_value=set()))
    monkeypatch.setattr(collector, "get_or_create_product", AsyncMock(return_value=product))
    monkeypatch.setattr(
        collector,
        "SCRAPERS",
        {"Tatcha 공홈": (_make_brand_scraper("Tatcha 공홈", "Tatcha", [ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0)], calls), "en")},
    )
    monkeypatch.setattr(collector, "persist_events_for_product", AsyncMock(return_value=(0, set())))

    result = await collector._collect_platform(product.id, "Tatcha 공홈", "", "US", force=True)

    assert result == {product.id}
    assert calls == [""]


@pytest.mark.asyncio
async def test_collect_platform_returns_authoritative_product_ids_from_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_product = Product(id=uuid.uuid4(), name_en="Search Placeholder", brand="Tatcha")
    authoritative_product_id = uuid.uuid4()
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    event = ScrapedEvent(
        product_name="Renamed Water Cream",
        brand="Tatcha",
        sale_price=70.0,
        external_id="40111",
        id_type="variant_id",
    )
    session = _CollectPlatformSession(source_product)
    monkeypatch.setattr(collector, "AsyncSessionLocal", lambda: _SweepSessionContext(session))
    monkeypatch.setattr(collector, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collector, "_fresh_platforms", AsyncMock(return_value=set()))
    monkeypatch.setattr(collector, "_translate", lambda query, target_lang: query)
    monkeypatch.setattr(collector, "resolve_product_by_external_id", AsyncMock(return_value=None))
    monkeypatch.setattr(collector, "get_or_create_product", AsyncMock(return_value=source_product))
    monkeypatch.setattr(
        collector,
        "SCRAPERS",
        {"Tatcha 공홈": (_make_brand_scraper("Tatcha 공홈", "Tatcha", [event], calls), "en")},
    )
    monkeypatch.setattr(collector, "_scraper_instances", {})
    monkeypatch.setattr(
        collector,
        "persist_events_for_product",
        AsyncMock(return_value=(1, {authoritative_product_id})),
    )

    result = await collector._collect_platform(source_product.id, "Tatcha 공홈", "", "US", force=True)

    assert result == {authoritative_product_id}
    assert source_product.id not in result
    assert calls == [""]


@pytest.mark.asyncio
async def test_collect_platform_external_id_fast_path_skips_name_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    seed_product = Product(id=uuid.uuid4(), name_en="Original Name", brand="Tatcha")
    mapped_product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    event = ScrapedEvent(
        product_name="Renamed Water Cream",
        brand="Tatcha",
        sale_price=70.0,
        external_id="40111",
        id_type="variant_id",
    )
    session = _CollectPlatformSession(seed_product)
    monkeypatch.setattr(collector, "AsyncSessionLocal", lambda: _SweepSessionContext(session))
    monkeypatch.setattr(collector, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collector, "_fresh_platforms", AsyncMock(return_value=set()))
    monkeypatch.setattr(collector, "_translate", lambda query, target_lang: query)
    monkeypatch.setattr(collector, "resolve_product_by_external_id", AsyncMock(return_value=mapped_product))
    monkeypatch.setattr(collector, "get_or_create_product", AsyncMock(side_effect=AssertionError("name matching must not run")))
    monkeypatch.setattr(
        collector,
        "SCRAPERS",
        {"Tatcha 공홈": (_make_brand_scraper("Tatcha 공홈", "Tatcha", [event], calls), "en")},
    )
    monkeypatch.setattr(collector, "_scraper_instances", {})
    monkeypatch.setattr(collector, "persist_events_for_product", AsyncMock(return_value=(1, {mapped_product.id})))

    result = await collector._collect_platform(seed_product.id, "Tatcha 공홈", "", "US", force=True)

    assert result == {mapped_product.id}
    assert calls == [""]


@pytest.mark.asyncio
async def test_collect_all_external_id_fast_path_skips_exact_match(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    platform = Platform(id=uuid.uuid4(), name="Tatcha 공홈", country="US")
    calls: list[str] = []
    event = ScrapedEvent(
        product_name="The Water Cream 2026",
        brand="Tatcha",
        sale_price=70.0,
        external_id="40111",
        id_type="variant_id",
    )
    _patch_sweep_runtime(
        monkeypatch,
        brand_scrapers={"Tatcha 공홈": _make_brand_scraper("Tatcha 공홈", "Tatcha", [event], calls)},
    )
    monkeypatch.setattr(collect, "get_platform", AsyncMock(return_value=platform))
    monkeypatch.setattr(collect, "resolve_product_by_external_id", AsyncMock(return_value=product))
    monkeypatch.setattr(collect, "find_exact_for_sweep", AsyncMock(side_effect=AssertionError("exact match must not run")))
    monkeypatch.setattr(collect, "persist_events_for_product", AsyncMock(return_value=(1, set())))

    result = await collect._collect_all()

    assert result == 1
    assert calls == [""]


@pytest.mark.asyncio
async def test_resolve_product_by_external_id_skips_item_code(monkeypatch: pytest.MonkeyPatch) -> None:
    product = Product(id=uuid.uuid4(), name_en="The Water Cream", brand="Tatcha")
    find_by_external_id = AsyncMock(return_value=product)
    monkeypatch.setattr(collector, "find_by_external_id", find_by_external_id)

    result = await collector.resolve_product_by_external_id(
        MagicMock(),
        uuid.uuid4(),
        [
            ScrapedEvent(product_name="Rakuten listing", external_id="shop:100", id_type="item_code"),
            ScrapedEvent(product_name="Shopify listing", external_id="40111", id_type="variant_id"),
        ],
    )

    assert result is product
    find_by_external_id.assert_awaited_once()
    assert find_by_external_id.await_args.args[2] == "40111"


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
@pytest.mark.asyncio
async def test_live_pg_shopify_two_runs_keep_single_platform_product_id_mapping() -> None:
    marker = f"platform-id-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        product = Product(name_en=marker, brand="Test Brand")
        platform = Platform(name=marker, country="US")
        db.add(product)
        db.add(platform)
        await db.commit()
        await db.refresh(product)
        await db.refresh(platform)

        event = ScrapedEvent(
            product_name=marker,
            brand="Test Brand",
            sale_price=10.0,
            currency="USD",
            start_date=date(2026, 8, 18),
            confidence=0.95,
            external_id="variant-1",
            id_type="variant_id",
        )

        first, first_used_product_ids = await collector.persist_events_for_product(db, product, platform, [event])
        second, second_used_product_ids = await collector.persist_events_for_product(db, product, platform, [event])
        rows = (
            await db.execute(
                select(PlatformProductId).where(
                    PlatformProductId.platform_id == platform.id,
                    PlatformProductId.external_id == "variant-1",
                )
            )
        ).scalars().all()

        assert first == 1
        assert second == 0
        assert first_used_product_ids == {product.id}
        assert second_used_product_ids == {product.id}
        assert len(rows) == 1
        assert rows[0].product_id == product.id

        await db.execute(delete(PlatformProductId).where(PlatformProductId.platform_id == platform.id))
        await db.execute(delete(SaleEvent).where(SaleEvent.product_id == product.id))
        await db.execute(delete(Product).where(Product.id == product.id))
        await db.execute(delete(Platform).where(Platform.id == platform.id))
        await db.commit()


@pytest.mark.skipif(LIVE_PG_UNAVAILABLE, reason=LIVE_PG_MARK_REASON)
@pytest.mark.asyncio
async def test_live_pg_upsert_keeps_active_existing_product_and_reassigns_deleted_product() -> None:
    marker = f"platform-id-{uuid.uuid4()}"
    async with AsyncSessionLocal() as db:
        platform = Platform(name=marker, country="US")
        first = Product(name_en=f"{marker}-first", brand="Test Brand")
        second = Product(name_en=f"{marker}-second", brand="Test Brand")
        third = Product(name_en=f"{marker}-third", brand="Test Brand")
        db.add_all([platform, first, second, third])
        await db.commit()
        await db.refresh(platform)
        await db.refresh(first)
        await db.refresh(second)
        await db.refresh(third)

        first_result = await collector.upsert_platform_product_id(
            db, first.id, platform.id, "variant-1", "variant_id"
        )
        active_conflict_result = await collector.upsert_platform_product_id(
            db, second.id, platform.id, "variant-1", "variant_id"
        )
        assert first_result == first.id
        assert active_conflict_result == first.id

        first.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        deleted_result = await collector.upsert_platform_product_id(
            db, second.id, platform.id, "variant-1", "variant_id"
        )
        assert deleted_result == second.id

        second.deleted_at = datetime.now(timezone.utc)
        await db.commit()
        repeated_deleted_result = await collector.upsert_platform_product_id(
            db, third.id, platform.id, "variant-1", "variant_id"
        )
        assert repeated_deleted_result == third.id

        rows = (
            await db.execute(
                select(PlatformProductId).where(
                    PlatformProductId.platform_id == platform.id,
                    PlatformProductId.external_id == "variant-1",
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].product_id == third.id

        await db.execute(delete(PlatformProductId).where(PlatformProductId.platform_id == platform.id))
        await db.execute(delete(Product).where(Product.id.in_([first.id, second.id, third.id])))
        await db.execute(delete(Platform).where(Platform.id == platform.id))
        await db.commit()
