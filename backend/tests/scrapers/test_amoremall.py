"""아모레몰 스크래퍼 단위 테스트 (실제 HTTP/Playwright 호출 없음)."""
import pytest
from bs4 import BeautifulSoup

from app.scrapers.brands.amoremall import (
    AmoremallScraper,
    _parse_card,
    _parse_price,
    _parse_rate,
)

# ---------------------------------------------------------------------------
# 헬퍼 함수 테스트
# ---------------------------------------------------------------------------


def test_parse_price_with_comma() -> None:
    assert _parse_price("38,000원") == 38000.0


def test_parse_price_plain_number() -> None:
    assert _parse_price("19900") == 19900.0


def test_parse_price_none_on_text() -> None:
    assert _parse_price("가격 미정") is None


def test_parse_rate_percent() -> None:
    assert _parse_rate("30%") == 30.0


def test_parse_rate_with_space() -> None:
    assert _parse_rate("15 % OFF") == 15.0


def test_parse_rate_none() -> None:
    assert _parse_rate("할인 없음") is None


# ---------------------------------------------------------------------------
# _parse_card 순수 함수 테스트 — 픽스처 HTML 사용
# ---------------------------------------------------------------------------

_CARD_HTML_FULL = """
<div class="prd-item">
  <span class="brand-name">설화수</span>
  <span class="prd-name">윤조에센스 60ml</span>
  <del class="original-price">95,000원</del>
  <span class="sale-price">76,000원</span>
  <span class="discount-rate">20%</span>
  <span class="badge">단독</span>
  <span class="badge">멤버스</span>
</div>
"""

_CARD_HTML_SALE_ONLY = """
<div class="prd-item">
  <span class="prd-name">아이오페 레티놀 엑스퍼트</span>
  <span class="sale-price">62,000원</span>
</div>
"""

_CARD_HTML_NO_PRICE = """
<div class="prd-item">
  <span class="prd-name">라네즈 워터슬리핑마스크</span>
</div>
"""

_CARD_HTML_CALC_DISCOUNT = """
<div class="prd-item">
  <span class="prd-name">한율 어성초 진정에센스</span>
  <del class="original-price">28,000원</del>
  <span class="sale-price">22,400원</span>
</div>
"""


def _make_card(html: str, selector: str = ".prd-item") -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    return soup.select_one(selector)  # type: ignore[return-value]


SOURCE_URL = "https://www.amoremall.com/kr/ko/search?query=에센스"
QUERY = "에센스"


def test_parse_card_full_data() -> None:
    """정가+할인가+배지 모두 있을 때 confidence=0.8, reason 포함."""
    card = _make_card(_CARD_HTML_FULL)
    event = _parse_card(card, SOURCE_URL, QUERY)

    assert event.product_name == "윤조에센스 60ml"
    assert event.brand == "설화수"
    assert event.original_price == 95000.0
    assert event.sale_price == 76000.0
    assert event.discount_rate == 20.0
    assert event.currency == "KRW"
    assert event.confidence == 0.8
    assert event.reason is not None
    assert "단독" in event.reason
    assert "멤버스" in event.reason
    assert event.source_url == SOURCE_URL


def test_parse_card_sale_price_only() -> None:
    """할인가만 있을 때 confidence=0.5."""
    card = _make_card(_CARD_HTML_SALE_ONLY)
    event = _parse_card(card, SOURCE_URL, QUERY)

    assert event.product_name == "아이오페 레티놀 엑스퍼트"
    assert event.sale_price == 62000.0
    assert event.original_price is None
    assert event.confidence == 0.5
    assert event.currency == "KRW"


def test_parse_card_no_price() -> None:
    """가격 정보 없을 때 confidence=0, raw_text 보존."""
    card = _make_card(_CARD_HTML_NO_PRICE)
    event = _parse_card(card, SOURCE_URL, QUERY)

    assert event.confidence == 0.0
    assert event.raw_text is not None
    assert len(event.raw_text) > 0


def test_parse_card_discount_rate_calculated() -> None:
    """할인율 직접 표시 없을 때 정가-할인가로 계산."""
    card = _make_card(_CARD_HTML_CALC_DISCOUNT)
    event = _parse_card(card, SOURCE_URL, QUERY)

    assert event.original_price == 28000.0
    assert event.sale_price == 22400.0
    # (1 - 22400/28000) * 100 = 20.0
    assert event.discount_rate == pytest.approx(20.0, abs=0.1)
    assert event.confidence == 0.8


# ---------------------------------------------------------------------------
# 스크래퍼 클래스 속성 테스트
# ---------------------------------------------------------------------------


def test_scraper_platform_attrs() -> None:
    scraper = AmoremallScraper()
    assert scraper.PLATFORM_NAME == "아모레몰"
    assert scraper.COUNTRY == "KR"
    assert scraper.RATE_LIMIT_SEC == 2.0


# ---------------------------------------------------------------------------
# Playwright 실제 네트워크 호출은 스킵
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="실제 Playwright/네트워크 호출 — CI에서 스킵")
async def test_scrape_live() -> None:  # pragma: no cover
    scraper = AmoremallScraper()
    events = await scraper.scrape("세럼")
    assert isinstance(events, list)
