"""Slickdeals 딜 신호 파싱 — 추가 소스(대체 아님)."""
from datetime import timedelta
from email.utils import format_datetime

import pytest

from app.scrapers import slickdeals
from app.scrapers.slickdeals import parse_feed, parse_price


def _item(title: str, hours_ago: float = 1.0, link: str = "https://slickdeals.net/f/1") -> str:
    when = format_datetime(slickdeals.now_utc() - timedelta(hours=hours_ago))
    return f"<item><title><![CDATA[{title}]]></title><link>{link}</link><pubDate>{when}</pubDate></item>"


def test_extracts_brand_and_price_from_title() -> None:
    xml = _item("Torriden DIVE-IN Serum Set 1.69 oz $14.9")
    signals = parse_feed(xml)
    assert len(signals) == 1
    assert signals[0].brand == "Torriden"
    assert signals[0].price == 14.9


def test_price_with_thousands_separator() -> None:
    assert parse_price("La Prairie Cream $1,299.00") == 1299.0
    assert parse_price("no price here") is None


def test_items_without_a_known_brand_are_skipped() -> None:
    assert parse_feed(_item("Generic Lotion 40% off $9.99")) == []


def test_stale_items_are_dropped() -> None:
    """48시간 넘은 딜은 이미 끝났을 가능성이 높다."""
    assert parse_feed(_item("Kiehl's Sitewide 25% off", hours_ago=200)) == []


def test_sitewide_retailer_promo_is_captured() -> None:
    """브랜드 사이트와이드 세일이 우리에겐 가장 값진 신호다."""
    signals = parse_feed(_item("25% Off Sitewide: Kiehl's Skincare Back to School Sale"))
    assert signals and signals[0].brand == "Kiehl's"


def test_malformed_dates_do_not_crash() -> None:
    xml = "<item><title>Tatcha deal</title><link>x</link><pubDate>garbage</pubDate></item>"
    assert parse_feed(xml) == []


@pytest.mark.asyncio
async def test_fetch_failure_yields_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, *a: object, **kw: object) -> object:
            raise RuntimeError("down")

    monkeypatch.setattr(slickdeals.httpx, "AsyncClient", lambda **kw: _Boom())
    assert await slickdeals.fetch_deal_signals("beauty") == []
