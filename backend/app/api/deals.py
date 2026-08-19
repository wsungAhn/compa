"""Deal signal feed API backed by short-lived social posts."""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.sale_windows import parse_discount_pct
from app.models.social_post import SocialPost

router = APIRouter(tags=["deals"])

_SUPPORTED_PLATFORMS = ("reddit", "slickdeals")
_CONTENT_RE = re.compile(r"^\[(?P<brand>[^\]]+)\]\s*(?P<rest>.+)$")
_PRICE_RE = re.compile(r"\s*\(\$(?P<price>[\d,.]+)\)\s*$")


class DealSignalOut(BaseModel):
    id: uuid.UUID
    brand: str | None
    title: str
    discount_pct: float | None
    price: str | None
    source: str
    source_url: str | None
    posted_at: datetime | None


def _parse_content(content: str | None) -> tuple[str | None, str, str | None, float | None]:
    """Parse the read-only display fields from SocialPost.content without inventing data."""
    raw = content or ""
    brand: str | None = None
    rest = raw

    match = _CONTENT_RE.match(raw)
    if match:
        brand = match.group("brand")
        rest = match.group("rest")

    price: str | None = None
    price_match = _PRICE_RE.search(rest)
    if price_match:
        price = price_match.group("price")
        rest = _PRICE_RE.sub("", rest)

    title = rest
    discount_pct = parse_discount_pct(title)
    return brand, title, price, discount_pct


def _to_deal_signal(post: SocialPost) -> DealSignalOut:
    brand, title, price, discount_pct = _parse_content(post.content)
    return DealSignalOut(
        id=post.id,
        brand=brand,
        title=title,
        discount_pct=discount_pct,
        price=price,
        source=post.platform,
        source_url=post.post_url,
        posted_at=post.posted_at,
    )


@router.get("/api/deals", response_model=list[DealSignalOut])
async def list_deal_signals(limit: int = Query(50, ge=1, le=100)) -> list[DealSignalOut]:
    async with AsyncSessionLocal() as db:
        rows = (
            await db.execute(
                select(SocialPost)
                .where(SocialPost.platform.in_(_SUPPORTED_PLATFORMS))
                .order_by(SocialPost.posted_at.desc().nullslast(), SocialPost.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
    return [_to_deal_signal(row) for row in rows]
