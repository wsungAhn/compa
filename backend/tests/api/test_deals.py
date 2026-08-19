"""Tests for the public deal signal feed API."""
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import deals
from app.models.social_post import SocialPost


class _ScalarResult:
    def __init__(self, rows: list[SocialPost]) -> None:
        self._rows = rows

    def all(self) -> list[SocialPost]:
        return self._rows


class _ExecuteResult:
    def __init__(self, rows: list[SocialPost]) -> None:
        self._rows = rows

    def scalars(self) -> _ScalarResult:
        return _ScalarResult(self._rows)


class _Session:
    def __init__(self, rows: list[SocialPost]) -> None:
        self._rows = rows

    async def __aenter__(self) -> "_Session":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def execute(self, query: object) -> _ExecuteResult:
        return _ExecuteResult(self._rows)


def _post(
    *,
    platform: str,
    content: str,
    posted_at: datetime | None = None,
    url: str | None = "https://example.test/deal",
) -> SocialPost:
    return SocialPost(
        id=uuid4(),
        platform=platform,
        post_url=url,
        content=content,
        posted_at=posted_at,
    )


async def test_list_deals_parses_content_without_inventing_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    posted_at = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
    rows = [
        _post(
            platform="slickdeals",
            content="[코스알엑스] 40% off Advanced Snail ($15.29)",
            posted_at=posted_at,
        ),
        _post(platform="reddit", content="Unbranded thread with no discount", url=None),
    ]
    monkeypatch.setattr(deals, "AsyncSessionLocal", MagicMock(return_value=_Session(rows)))

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/deals")

    assert response.status_code == 200
    body = response.json()
    assert body[0] == {
        "id": str(rows[0].id),
        "brand": "코스알엑스",
        "title": "40% off Advanced Snail",
        "discount_pct": 40.0,
        "price": "15.29",
        "source": "slickdeals",
        "source_url": "https://example.test/deal",
        "posted_at": "2026-08-19T12:00:00Z",
    }
    assert body[1]["brand"] is None
    assert body[1]["title"] == "Unbranded thread with no discount"
    assert body[1]["discount_pct"] is None
    assert body[1]["price"] is None
    assert body[1]["source"] == "reddit"
    assert body[1]["source_url"] is None


def test_parse_content_keeps_unmatched_price_like_text_in_title() -> None:
    brand, title, price, discount_pct = deals._parse_content("[Brand] bundle (€15)")

    assert brand == "Brand"
    assert title == "bundle (€15)"
    assert price is None
    assert discount_pct is None
