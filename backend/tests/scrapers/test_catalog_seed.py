"""catalog 시딩 로직 단위 테스트 — Naver 게이팅·HTML 정리·멱등성·빈 테이블 가드."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.product import Product
from app.scrapers import catalog


class _ScalarResult:
    def __init__(self, value: Product | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> Product | None:
        return self._value


class FakeSession:
    """seed_catalog가 사용하는 execute/add/commit/rollback만 흉내내는 가짜 세션."""

    def __init__(self, initial: Product | None = None) -> None:
        self.existing_names: set[str] = set()
        self.added: list[Product] = []
        self.commits = 0
        self.rollbacks = 0
        self._initial = initial

    async def execute(self, statement: object) -> _ScalarResult:
        # seed_catalog_if_empty 의 select(Product).limit(1) 초기 확인
        if self._initial is not None:
            return _ScalarResult(self._initial)
        compiled = str(statement.compile(compile_kwargs={"literal_binds": True}))
        for name in self.existing_names:
            if name in compiled:
                return _ScalarResult(Product(name_kr=name, name_en=name, brand="existing"))
        return _ScalarResult(None)

    def add(self, product: Product) -> None:
        self.added.append(product)
        if product.name_kr:
            self.existing_names.add(product.name_kr)

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def _patch_naver_enabled(monkeypatch: MagicMock, enabled: bool) -> None:
    keys = {"네이버쇼핑": object()} if enabled else {}
    monkeypatch.setattr(catalog, "get_enabled_scrapers", lambda: keys, raising=False)
    monkeypatch.setattr(
        "app.scrapers.collector.get_enabled_scrapers", lambda: keys
    )


@pytest.mark.asyncio
async def test_seed_catalog_skips_without_naver_keys(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(
        "app.core.config.settings",
        MagicMock(naver_client_id="", naver_client_secret=""),
    )

    result = await catalog.seed_catalog(FakeSession(), brands=["설화수"])  # type: ignore[arg-type]

    assert result == 0


@pytest.mark.asyncio
async def test_seed_catalog_skips_when_naver_disabled(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(
        "app.core.config.settings",
        MagicMock(naver_client_id="id", naver_client_secret="secret"),
    )
    _patch_naver_enabled(monkeypatch, enabled=False)

    result = await catalog.seed_catalog(FakeSession(), brands=["설화수"])  # type: ignore[arg-type]

    assert result == 0


@pytest.mark.asyncio
async def test_seed_catalog_cleans_html_and_is_idempotent(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(
        "app.core.config.settings",
        MagicMock(naver_client_id="id", naver_client_secret="secret"),
    )
    _patch_naver_enabled(monkeypatch, enabled=True)
    monkeypatch.setattr(catalog.asyncio, "sleep", AsyncMock())

    scraper = MagicMock()
    scraper._search_products = AsyncMock(
        return_value=[
            SimpleNamespace(title="설화수 <b>윤조에센스</b>", brand="설화수"),
            SimpleNamespace(title="설화수 <b>윤조에센스</b>", brand="설화수"),  # 중복
        ]
    )
    monkeypatch.setattr("app.scrapers.kr.naver_shop.NaverShopScraper", lambda: scraper)

    session = FakeSession()
    result = await catalog.seed_catalog(session, brands=["설화수"])  # type: ignore[arg-type]

    assert result == 1
    assert [p.name_kr for p in session.added] == ["설화수 윤조에센스"]


@pytest.mark.asyncio
async def test_seed_catalog_if_empty_skips_when_products_exist(monkeypatch: MagicMock) -> None:
    called = AsyncMock(return_value=0)
    monkeypatch.setattr(catalog, "seed_catalog", called)

    session = FakeSession(initial=Product(name_kr="기존제품", name_en="existing", brand="b"))
    await catalog.seed_catalog_if_empty(session)  # type: ignore[arg-type]

    called.assert_not_called()


@pytest.mark.asyncio
async def test_seed_catalog_if_empty_seeds_when_empty(monkeypatch: MagicMock) -> None:
    called = AsyncMock(return_value=0)
    monkeypatch.setattr(catalog, "seed_catalog", called)

    await catalog.seed_catalog_if_empty(FakeSession())  # type: ignore[arg-type]

    called.assert_called_once()
