"""catalog 시딩 로직 단위 테스트 — 브랜드 필터·멱등성·상한·실패 격리·빈 테이블 가드."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.product import Product
from app.scrapers import catalog
from app.scrapers.base import ScrapedEvent


class _ScalarResult:
    def __init__(self, value: Product | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Product | None:
        return self._value


class FakeSession:
    """seed_catalog가 쓰는 execute/add/commit/rollback만 흉내내는 가짜 세션."""

    def __init__(self, initial: Product | None = None) -> None:
        self.existing_names: set[str] = set()
        self.added: list[Product] = []
        self.commits = 0
        self.rollbacks = 0
        self._initial = initial

    async def execute(self, statement: object) -> _ScalarResult:
        if self._initial is not None:
            return _ScalarResult(self._initial)
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]
        for name in self.existing_names:
            if name in compiled:
                return _ScalarResult(Product(name_en=name, brand="existing"))
        return _ScalarResult(None)

    def add(self, product: Product) -> None:
        self.added.append(product)
        if product.name_en:
            self.existing_names.add(product.name_en)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _fake_registry(monkeypatch: MagicMock, events: list[ScrapedEvent]) -> None:
    class _Scraper:
        async def scrape(self, query: str) -> list[ScrapedEvent]:
            return events

    monkeypatch.setattr(catalog, "BRAND_SCRAPERS", {"Tatcha 공홈": _Scraper})
    monkeypatch.setattr(catalog.asyncio, "sleep", AsyncMock())


@pytest.mark.asyncio
async def test_seeds_products_from_brand_catalog(monkeypatch: MagicMock) -> None:
    _fake_registry(monkeypatch, [
        ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0),
        ScrapedEvent(product_name="The Water Cream", brand="Tatcha", sale_price=70.0),  # 중복
    ])

    session = FakeSession()
    result = await catalog.seed_catalog(session, brands=["Tatcha 공홈"])  # type: ignore[arg-type]

    assert result == 1
    assert [p.name_en for p in session.added] == ["The Water Cream"]
    assert session.added[0].brand == "Tatcha"


@pytest.mark.asyncio
async def test_failed_events_are_not_seeded(monkeypatch: MagicMock) -> None:
    """confidence=0은 수집 실패 신호다 — 제품으로 만들면 안 된다."""
    _fake_registry(monkeypatch, [
        ScrapedEvent(product_name="broken", confidence=0.0, raw_text="blocked"),
    ])

    session = FakeSession()
    assert await catalog.seed_catalog(session, brands=["Tatcha 공홈"]) == 0  # type: ignore[arg-type]
    assert session.added == []


@pytest.mark.asyncio
async def test_caps_products_per_brand(monkeypatch: MagicMock) -> None:
    _fake_registry(monkeypatch, [
        # 고정폭 이름 — 가짜 세션은 부분문자열로 중복을 판정하므로 P1이 P10에 걸린다
        ScrapedEvent(product_name=f"P{i:05d}", brand="Tatcha", sale_price=1.0)
        for i in range(catalog.MAX_PER_BRAND + 25)
    ])

    session = FakeSession()
    result = await catalog.seed_catalog(session, brands=["Tatcha 공홈"])  # type: ignore[arg-type]

    assert result == catalog.MAX_PER_BRAND


@pytest.mark.asyncio
async def test_unknown_brand_is_ignored(monkeypatch: MagicMock) -> None:
    _fake_registry(monkeypatch, [ScrapedEvent(product_name="x", sale_price=1.0)])

    session = FakeSession()
    assert await catalog.seed_catalog(session, brands=["없는 브랜드"]) == 0  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_one_broken_brand_does_not_abort_the_rest(monkeypatch: MagicMock) -> None:
    class _Broken:
        async def scrape(self, query: str) -> list[ScrapedEvent]:
            raise RuntimeError("boom")

    class _Good:
        async def scrape(self, query: str) -> list[ScrapedEvent]:
            return [ScrapedEvent(product_name="Good One", brand="B", sale_price=1.0)]

    monkeypatch.setattr(catalog, "BRAND_SCRAPERS", {"A 공홈": _Broken, "B 공홈": _Good})
    monkeypatch.setattr(catalog.asyncio, "sleep", AsyncMock())

    session = FakeSession()
    result = await catalog.seed_catalog(session)  # type: ignore[arg-type]

    assert result == 1
    assert session.rollbacks == 1


@pytest.mark.asyncio
async def test_seed_catalog_if_empty_skips_when_products_exist(monkeypatch: MagicMock) -> None:
    called = AsyncMock(return_value=0)
    monkeypatch.setattr(catalog, "seed_catalog", called)

    session = FakeSession(initial=Product(name_en="existing", brand="b"))
    await catalog.seed_catalog_if_empty(session)  # type: ignore[arg-type]

    called.assert_not_called()


@pytest.mark.asyncio
async def test_seed_catalog_if_empty_seeds_when_empty(monkeypatch: MagicMock) -> None:
    called = AsyncMock(return_value=0)
    monkeypatch.setattr(catalog, "seed_catalog", called)

    await catalog.seed_catalog_if_empty(FakeSession())  # type: ignore[arg-type]

    called.assert_called_once()
