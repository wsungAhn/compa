"""Slickdeals 딜 신호 — Reddit과 나란히 두는 추가 소스.

소스는 대체가 아니라 누적이다. Reddit은 커뮤니티가 올린 딜을, Slickdeals는 리테일러
프로모션을 더 두껍게 본다(2026-08-06 실측: `beauty` 쿼리 48시간 내 12건, 최신 3.2시간
전 — 살아 있다).

Reddit과 달리 48시간 삭제 의무가 없다. 그건 Reddit Data API Terms가 자기 플랫폼의
User Content에 부과한 계약 조건이고, 여기에 적용할 근거가 없다. 오히려 과거 딜 이력은
"이 세일이 반복되는가"를 판단할 재료라 남기는 쪽이 맞다.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from app.scrapers.brand_dictionary import detect_brand
from app.scrapers.reddit_deals import now_utc

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; compa/0.1; +https://compa.mwco.io)"
FEED_URL = "https://slickdeals.net/newsearch.php?src=SearchBarV2&q={query}&searchin=first&rss=1"

# 실측 신선도: beauty 48h내 12건(중앙값 48h), skincare 8건. sephora/ulta 단독 쿼리는
# 매물이 적어 거의 죽어 있었다 — 넓은 카테고리 쿼리가 낫다.
QUERIES = ("beauty", "skincare")
MAX_AGE_HOURS = 48
TIMEOUT_SECONDS = 20.0
# Slickdeals는 Reddit 같은 빡빡한 무인증 한도가 관측되지 않았지만, 예의상 간격을 둔다.
MIN_INTERVAL_SECONDS = 5

_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
_TITLE_RE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.S)
_LINK_RE = re.compile(r"<link>(.*?)</link>", re.S)
_DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")

# 제목에 박혀 오는 가격 — "$14.9", "$1,299.00"
PRICE_RE = re.compile(r"\$\s?(\d{1,4}(?:,\d{3})*(?:\.\d{1,2})?)")


@dataclass(frozen=True)
class DealSignal:
    title: str
    url: str
    brand: str
    posted_at: datetime
    price: float | None


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text)).strip()


def parse_price(title: str) -> float | None:
    match = PRICE_RE.search(title)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_feed(xml: str, max_age_hours: int = MAX_AGE_HOURS) -> list[DealSignal]:
    """RSS → 브랜드가 잡히고 충분히 최신인 딜만."""
    cutoff = now_utc() - timedelta(hours=max_age_hours)
    signals: list[DealSignal] = []
    for raw in _ITEM_RE.findall(xml):
        title_match = _TITLE_RE.search(raw)
        date_match = _DATE_RE.search(raw)
        if not (title_match and date_match):
            continue
        title = _clean(title_match.group(1))
        try:
            posted_at = parsedate_to_datetime(date_match.group(1).strip())
        except (TypeError, ValueError):
            continue
        if posted_at.tzinfo is None or posted_at < cutoff:
            continue
        brand = detect_brand(title)
        if not brand:
            continue
        link_match = _LINK_RE.search(raw)
        signals.append(
            DealSignal(
                title=title,
                url=_clean(link_match.group(1)) if link_match else "",
                brand=brand,
                posted_at=posted_at,
                price=parse_price(title),
            )
        )
    return signals


async def fetch_deal_signals(query: str) -> list[DealSignal]:
    """쿼리 1회 조회. 실패하면 이번 회차를 포기한다."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = await client.get(
                FEED_URL.format(query=query), headers={"User-Agent": USER_AGENT}
            )
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("slickdeals '%s' fetch failed: %s", query, exc)
        return []
    return parse_feed(resp.text)


async def fetch_all(queries: tuple[str, ...] = QUERIES) -> list[DealSignal]:
    import asyncio

    collected: list[DealSignal] = []
    for index, query in enumerate(queries):
        if index:
            await asyncio.sleep(MIN_INTERVAL_SECONDS)
        collected.extend(await fetch_deal_signals(query))
    return collected
