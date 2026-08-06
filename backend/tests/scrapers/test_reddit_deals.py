"""Reddit 딜 신호 파싱·필터·UA 규약 테스트 (실제 HTTP 호출 없음)."""
import re
from datetime import timedelta

import pytest

from app.scrapers import reddit_deals
from app.scrapers.reddit_deals import (
    USER_AGENT,
    DealSignal,
    fetch_deal_signals,
    match_brand,
    parse_feed,
)

BRANDS = ["Glossier", "Laneige", "Tatcha", "SK-II"]


def _fresh() -> str:
    return (reddit_deals.now_utc() - timedelta(hours=1)).isoformat()


def _entry(title: str, url: str = "https://reddit.com/r/beautydeals/x", updated: str | None = None) -> str:
    updated = updated or _fresh()
    return (
        f"<entry><title>{title}</title>"
        f'<link href="{url}"/>'
        f"<updated>{updated}</updated></entry>"
    )


def test_user_agent_matches_reddit_required_format() -> None:
    """Reddit이 형식을 강제하고 "NEVER lie about your User-Agent"라고 명시한다."""
    assert re.fullmatch(r"[\w.\-]+:[\w.\-]+:v[\d.]+ \(by /u/[\w\-]+\)", USER_AGENT)


def test_keeps_only_deal_titles_with_a_known_brand() -> None:
    xml = (
        _entry("10% off Glossier")                      # 딜 + 브랜드 → 유지
        + _entry("Glossier haul review")                # 브랜드만, 딜 아님 → 제외
        + _entry("30% off some random brand")           # 딜만, 브랜드 아님 → 제외
        + _entry("Laneige sale at Target")              # 유지
    )
    signals = parse_feed(xml, BRANDS)
    assert [s.brand for s in signals] == ["Glossier", "Laneige"]
    assert signals[0].title == "10% off Glossier"


def test_html_entities_and_tags_are_cleaned() -> None:
    signals = parse_feed(_entry("20% off Tatcha &amp; more <b>today</b>"), BRANDS)
    assert signals[0].title == "20% off Tatcha & more today"


def test_posted_at_is_parsed_as_aware_datetime() -> None:
    signals = parse_feed(_entry("15% off Glossier"), BRANDS)
    assert signals[0].posted_at is not None
    assert signals[0].posted_at.tzinfo is not None


def test_stale_posts_are_dropped() -> None:
    """new.rss에 8년 전 글이 섞여 온다(실측) — 지난 딜을 신호로 띄우면 안 된다."""
    old = (reddit_deals.now_utc() - timedelta(days=3000)).isoformat()
    assert parse_feed(_entry("10% off Glossier", updated=old), BRANDS) == []


def test_undated_posts_are_dropped() -> None:
    """날짜를 모르면 신선도를 보증할 수 없다."""
    assert parse_feed(_entry("10% off Glossier", updated="nonsense"), BRANDS) == []


def test_longest_alias_wins() -> None:
    """"sk2"가 "SK-II"를 가리지 않아야 한다."""
    assert match_brand("50% off SK-II essence", BRANDS) == "SK-II"
    assert match_brand("sk2 deal", BRANDS) == "SK-II"


class _Resp:
    def __init__(self, status: int, text: str = "") -> None:
        self.status_code = status
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def _client_returning(resp: _Resp, seen: dict[str, object]):  # type: ignore[no-untyped-def]
    class _Client:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, url: str, **kwargs: object) -> _Resp:
            seen["url"] = url
            seen.update(kwargs)
            return resp

    return lambda **kw: _Client()


@pytest.mark.asyncio
async def test_rate_limit_is_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    """무인증 클라이언트가 재시도로 한도를 두드리는 게 차단의 지름길이다."""
    seen: dict[str, object] = {}
    monkeypatch.setattr(reddit_deals.httpx, "AsyncClient", _client_returning(_Resp(429), seen))
    assert await fetch_deal_signals(BRANDS) == []


@pytest.mark.asyncio
async def test_request_sends_the_declared_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        reddit_deals.httpx,
        "AsyncClient",
        _client_returning(_Resp(200, _entry("10% off Glossier")), seen),
    )
    signals = await fetch_deal_signals(BRANDS)
    assert [s.brand for s in signals] == ["Glossier"]
    assert seen["headers"] == {"User-Agent": USER_AGENT}  # type: ignore[index]
    assert reddit_deals.SUBREDDIT in str(seen["url"])


@pytest.mark.asyncio
async def test_network_failure_yields_no_signals(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Boom:
        async def __aenter__(self):  # type: ignore[no-untyped-def]
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def get(self, *a: object, **kw: object) -> _Resp:
            raise RuntimeError("network down")

    monkeypatch.setattr(reddit_deals.httpx, "AsyncClient", lambda **kw: _Boom())
    assert await fetch_deal_signals(BRANDS) == []


def test_signal_is_immutable() -> None:
    """신호를 사후 수정해 가격처럼 쓰지 못하게 한다."""
    s = DealSignal(title="t", url="u", brand="Glossier", posted_at=None)
    with pytest.raises(Exception):
        s.title = "changed"  # type: ignore[misc]


def test_pacing_never_goes_below_the_measured_floor() -> None:
    """실측: 3초 1/6, 20초 3/6, 30초 4/6, 60초 6/6 — 60초가 바닥이다."""
    assert reddit_deals.MIN_INTERVAL_SECONDS == 60
    assert min(reddit_deals.INTERVAL_CHOICES) >= reddit_deals.MIN_INTERVAL_SECONDS
    assert {reddit_deals.next_interval() for _ in range(50)} <= set(reddit_deals.INTERVAL_CHOICES)


def test_pacing_is_not_a_fixed_period() -> None:
    """고정 주기는 그 자체로 기계 지문이다."""
    assert len(set(reddit_deals.INTERVAL_CHOICES)) > 1


@pytest.mark.asyncio
async def test_multi_subreddit_sweep_sleeps_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    async def fake_fetch(brands: list[str], subreddit: str = "") -> list[DealSignal]:
        return [DealSignal(title=f"10% off Glossier {subreddit}", url=f"u/{subreddit}",
                           brand="Glossier", posted_at=reddit_deals.now_utc())]

    monkeypatch.setattr(reddit_deals.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(reddit_deals, "fetch_deal_signals", fake_fetch)

    signals = await reddit_deals.fetch_all_subreddits(BRANDS, ("a", "b", "c"))

    assert len(signals) == 3
    # 첫 요청 앞에는 쉬지 않고, 이후 매 요청 앞에서 바닥 이상 쉰다.
    assert len(slept) == 2
    assert all(s >= reddit_deals.MIN_INTERVAL_SECONDS for s in slept)


def test_dead_subreddit_is_not_polled() -> None:
    """r/beautydeals는 new.rss 최신 글이 6년 전인 죽은 서브레딧이다(2026-08-06 실측).
    제목 밀도(딜성 14건)만 보면 좋아 보였지만 전부 과거 글이었다."""
    assert "beautydeals" not in reddit_deals.SUBREDDITS
