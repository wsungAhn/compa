"""Reddit 딜 신호 수집 — 가격 소스가 아니라 트리거.

무인증 RSS만 쓴다(`/r/{sub}/new.rss`). `/search.json`은 WAF 차단(403)이고,
검색 RSS도 429가 잦다 — 2026-08-06 실측: 3초 간격으로 두 번째 서브레딧부터 전부
429. 그래서 서브레딧 1개를 저빈도로만 친다.

Reddit은 User-Agent 형식을 강제하며 "NEVER lie about your User-Agent"라고 명시한다.
무인증 트래픽은 "차단하거나 스로틀할 수 있다"고 공지돼 있으므로, 실패 시 재시도하지
않고 그 회차를 포기한다(다음 주기에 또 온다).
"""
from __future__ import annotations

import asyncio
import html
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

logger = logging.getLogger(__name__)

# Reddit 지정 형식: <platform>:<app ID>:<version> (by /u/<username>)
USER_AGENT = "python:com.mwco.compa:v0.1.0 (by /u/wsungahn)"

# 2026-08-06 실측 — 간격별 6개 서브레딧 순회 성공률:
#   3초 1/6, 20초 3/6, 30초 4/6, 60초 **6/6**.
# 실패가 항상 3번째부터 시작한 것은 간격이 아니라 예산(토큰 버킷) 문제라는 뜻이고,
# 리필 속도가 대략 1req/60s다. 그래서 아래 페이싱은 60초를 바닥으로 잡는다.
MIN_INTERVAL_SECONDS = 60
# 고정 주기는 그 자체로 기계 지문이다. 바닥 이상에서 불규칙하게 고른다.
# 값이 딱 떨어지는 것(90/120/180)도 지문이 되므로 어중간한 수를 쓴다.
INTERVAL_CHOICES = (60, 76, 100, 200)

# 딜성 문구 밀도만 보면 beautydeals 14 / MUAontheCheap 23 / Ulta 9 였지만, 연령
# 분포를 재보니 beautydeals의 new.rss는 **최신 글이 6년 전**(중앙값 11년)인 죽은
# 서브레딧이었다 — 그 14건은 전부 과거 글이다. 제목 밀도만 보고 소스를 고르면 안 된다.
SUBREDDITS = ("MUAontheCheap", "Ulta")
SUBREDDIT = SUBREDDITS[0]
# new.rss에 오래된 글이 섞여 온다(2026-08-06 실측: 2018년 글이 반환됐다). 지난 딜을
# 신호로 띄우면 사용자를 헛걸음시키므로, 보존 한도와 같은 창으로 자른다.
MAX_AGE_HOURS = 48
FEED_URL = "https://www.reddit.com/r/{sub}/new.rss?limit=50"
TIMEOUT_SECONDS = 20.0

_ENTRY_RE = re.compile(r"<entry>(.*?)</entry>", re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
_LINK_RE = re.compile(r'<link[^>]*href="([^"]+)"')
_UPDATED_RE = re.compile(r"<updated>(.*?)</updated>", re.S)
_TAG_RE = re.compile(r"<[^>]+>")

# 딜성 문구 — 제목만으로 1차 선별한다(본문 파싱은 다음 레이어).
DEAL_RE = re.compile(
    r"\d{1,2}\s?%\s?off|\bsale\b|\bdeal\b|\bdiscount\b|\bcoupon\b|\bpromo\b|\bgwp\b|\bbogo\b",
    re.I,
)

# 브랜드 표기 변형 — 레지스트리 이름만으로는 못 잡는 것들.
BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    "SK-II": ("sk-ii", "skii", "sk2"),
    "innisfree": ("innisfree",),
    "Beauty of Joseon": ("beauty of joseon",),
}


@dataclass(frozen=True)
class DealSignal:
    """세일이 났다는 신호. 가격이 아니다 — 승격은 공홈 실가격 확인 후."""

    title: str
    url: str
    brand: str
    posted_at: datetime | None


def _clean(text: str) -> str:
    return html.unescape(_TAG_RE.sub("", text)).strip()


def _parse_updated(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def match_brand(title: str, brands: list[str]) -> str | None:
    """제목에 등장하는 브랜드. 가장 긴 매칭이 이긴다(SK2가 SK-II를 가리지 않도록)."""
    low = title.lower()
    hits: list[tuple[str, str]] = []
    for brand in brands:
        if brand.lower() in low:
            hits.append((brand, brand))
    for brand, aliases in BRAND_ALIASES.items():
        for alias in aliases:
            if alias in low:
                hits.append((brand, alias))
    if not hits:
        return None
    return max(hits, key=lambda h: len(h[1]))[0]


def parse_feed(xml: str, brands: list[str], max_age_hours: int = MAX_AGE_HOURS) -> list[DealSignal]:
    """RSS → 브랜드가 매칭됐고 충분히 최신인 딜 신호만."""
    cutoff = now_utc() - timedelta(hours=max_age_hours)
    signals: list[DealSignal] = []
    for raw_entry in _ENTRY_RE.findall(xml):
        title_match = _TITLE_RE.search(raw_entry)
        if not title_match:
            continue
        title = _clean(title_match.group(1))
        if not title or not DEAL_RE.search(title):
            continue
        brand = match_brand(title, brands)
        if not brand:
            continue
        link_match = _LINK_RE.search(raw_entry)
        updated_match = _UPDATED_RE.search(raw_entry)
        posted_at = _parse_updated(updated_match.group(1)) if updated_match else None
        # 날짜를 모르는 항목은 신선도를 보증할 수 없으므로 버린다.
        if posted_at is None or posted_at < cutoff:
            continue
        signals.append(
            DealSignal(
                title=title,
                url=link_match.group(1) if link_match else "",
                brand=brand,
                posted_at=posted_at,
            )
        )
    return signals


def next_interval() -> int:
    """다음 요청까지 기다릴 초. 측정된 바닥 이상에서 불규칙하게."""
    return random.choice(INTERVAL_CHOICES)


async def fetch_all_subreddits(
    brands: list[str], subreddits: tuple[str, ...] = SUBREDDITS
) -> list[DealSignal]:
    """여러 서브레딧을 사람 속도로 순회한다.

    첫 요청 뒤부터 MIN_INTERVAL_SECONDS 이상 불규칙하게 쉰다 — 실측상 이보다 촘촘하면
    3번째 요청부터 429가 난다.
    """
    collected: list[DealSignal] = []
    for index, sub in enumerate(subreddits):
        if index:
            await asyncio.sleep(next_interval())
        collected.extend(await fetch_deal_signals(brands, subreddit=sub))
    return collected


async def fetch_deal_signals(brands: list[str], subreddit: str = SUBREDDIT) -> list[DealSignal]:
    """한 서브레딧을 1회 조회. 실패하면 이번 회차를 포기한다(재시도 없음)."""
    url = FEED_URL.format(sub=subreddit)
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 429:
            # 무인증 클라이언트가 재시도로 한도를 두드리는 게 차단의 지름길이다.
            logger.warning("reddit r/%s rate limited (429) — skipping this round", subreddit)
            return []
        resp.raise_for_status()
    except Exception as exc:
        logger.warning("reddit r/%s fetch failed: %s", subreddit, exc)
        return []

    return parse_feed(resp.text, brands)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
