from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.scrapers import collector


def test_get_enabled_scrapers_default_safe_subset(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="네이버쇼핑,Rakuten"))

    enabled = collector.get_enabled_scrapers()

    assert list(enabled.keys()) == ["네이버쇼핑", "Rakuten"]


def test_get_enabled_scrapers_all(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="all"))

    enabled = collector.get_enabled_scrapers()

    assert enabled.keys() == collector.SCRAPERS.keys()


def test_get_enabled_scrapers_ignores_unknown_names(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="네이버쇼핑,Nope,Rakuten"))

    enabled = collector.get_enabled_scrapers()

    assert list(enabled.keys()) == ["네이버쇼핑", "Rakuten"]


def test_collect_fast_candidates_respect_enabled(monkeypatch: MagicMock) -> None:
    monkeypatch.setattr(collector, "settings", MagicMock(enabled_scrapers="Rakuten"))

    enabled_fast = [name for name in collector.FAST_SCRAPERS if name in collector.get_enabled_scrapers()]

    assert enabled_fast == []


@pytest.mark.asyncio
async def test_collect_fast_returns_only_products_with_events(monkeypatch: MagicMock) -> None:
    """collect_fast keeps query placeholder out of API results."""
    placeholder = MagicMock()
    placeholder.id = uuid4()
    collected_product = MagicMock()
    collected_product.id = uuid4()

    mock_db = AsyncMock(spec=AsyncSession)

    async def fake_get_or_create_product(
        db: AsyncSession,
        query: str,
        brand: str | None,
        country: str,
    ) -> MagicMock:
        assert query == "설화수"
        assert brand is None
        assert country == "KR"
        return placeholder

    async def fake_collect_platform(
        product_id: object,
        platform_name: str,
        query: str,
        platform_country: str,
        force: bool = False,
    ) -> set[object]:
        assert product_id == placeholder.id
        assert platform_name == "네이버쇼핑"
        assert query == "설화수"
        assert platform_country == "KR"
        assert force is False
        return {collected_product.id}

    async def fake_products_with_events(
        db: AsyncSession,
        product_ids: set[object],
    ) -> list[MagicMock]:
        assert product_ids == {collected_product.id}
        return [collected_product]

    monkeypatch.setattr(collector, "get_or_create_product", fake_get_or_create_product)
    monkeypatch.setattr(collector, "_collect_platform", fake_collect_platform)
    monkeypatch.setattr(collector, "_products_with_events", fake_products_with_events)
    monkeypatch.setattr(collector, "get_enabled_scrapers", lambda: {"네이버쇼핑": collector.SCRAPERS["네이버쇼핑"]})
    monkeypatch.setattr(collector, "FAST_SCRAPERS", {"네이버쇼핑"})
    monkeypatch.setattr(collector, "SKIP_SCRAPERS", set())

    products = await collector.collect_fast(mock_db, "설화수")

    assert products == [collected_product]
    assert placeholder not in products
