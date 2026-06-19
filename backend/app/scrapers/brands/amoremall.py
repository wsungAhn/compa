"""아모레몰(amoremall.com) 공홈 스크래퍼 — SPA이므로 Playwright + BeautifulSoup 사용."""
import logging
import re
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright

from app.core.proxy import playwright_proxy
from app.scrapers.base import BaseScraper, ScrapedEvent

_logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.amoremall.com/kr/ko/search?query={query}"

# 아모레몰 SPA 상품 카드 셀렉터 후보 목록 (우선순위 순)
_CARD_SELECTORS = [".prd-item", ".product-item", ".goods-item", ".item-wrap"]

# 가격 파싱 패턴
_PRICE_RE = re.compile(r"[\d,]+")
# 할인율 파싱 패턴 (예: "30%" 또는 "30% OFF")
_RATE_RE = re.compile(r"(\d+)\s*%")
# 세일 배지 키워드
_PROMO_KEYWORDS = {"단독", "멤버스", "특가", "할인", "세일", "쿠폰", "증정", "기획", "SALE"}


def _parse_price(text: str) -> float | None:
    """숫자+쉼표 패턴에서 가격 파싱."""
    cleaned = text.replace(",", "").replace("원", "").strip()
    m = _PRICE_RE.search(cleaned)
    return float(m.group()) if m else None


def _parse_rate(text: str) -> float | None:
    """텍스트에서 할인율(%) 파싱."""
    m = _RATE_RE.search(text)
    return float(m.group(1)) if m else None


def _extract_promo_reason(card: Tag) -> str | None:
    """카드에서 프로모션 문구(세일 배지 등)를 추출해 reason 필드용 텍스트 반환."""
    reasons: list[str] = []
    # 배지/라벨 요소 탐색
    for badge in card.select(".badge, .label, .tag, .flag, .promotion-flag, .prd-badge"):
        text = badge.get_text(strip=True)
        if text:
            reasons.append(text)
    # 키워드 포함 텍스트 탐색 (배지 없을 때 대비)
    if not reasons:
        full_text = card.get_text(separator=" ", strip=True)
        for kw in _PROMO_KEYWORDS:
            if kw in full_text:
                reasons.append(kw)
    return " | ".join(reasons) if reasons else None


def _parse_card(card: Tag, source_url: str, query: str) -> ScrapedEvent:
    """BeautifulSoup Tag(상품 카드)에서 ScrapedEvent 반환 — 순수 함수(테스트 가능).

    파싱 실패 시 confidence=0 + raw_text 보존, 예외 전파 금지.
    """
    raw_text = card.get_text(separator="\n", strip=True)
    try:
        # 상품명
        name_el = (
            card.select_one(".prd-name")
            or card.select_one(".product-name")
            or card.select_one(".goods-name")
            or card.select_one(".item-name")
        )
        product_name = name_el.get_text(strip=True) if name_el else query

        # 브랜드
        brand_el = (
            card.select_one(".brand-name")
            or card.select_one(".prd-brand")
            or card.select_one(".product-brand")
        )
        brand = brand_el.get_text(strip=True) if brand_el else None

        # 정가
        original_el = (
            card.select_one(".original-price")
            or card.select_one(".price-original")
            or card.select_one(".prd-price-original")
            or card.select_one(".tx-org")
            or card.select_one("del")  # 일반적으로 취소선 = 정가
        )
        original_price: float | None = None
        if original_el:
            original_price = _parse_price(original_el.get_text())

        # 할인가
        sale_el = (
            card.select_one(".sale-price")
            or card.select_one(".price-sale")
            or card.select_one(".prd-price-sale")
            or card.select_one(".tx-cur")
            or card.select_one(".selling-price")
        )
        sale_price: float | None = None
        if sale_el:
            sale_price = _parse_price(sale_el.get_text())

        # 정가/할인가 둘 다 없으면 일반 가격 영역에서 단일 가격 시도
        if original_price is None and sale_price is None:
            price_el = (
                card.select_one(".price")
                or card.select_one(".prd-price")
                or card.select_one(".product-price")
            )
            if price_el:
                sale_price = _parse_price(price_el.get_text())

        # 할인율
        rate_el = (
            card.select_one(".discount-rate")
            or card.select_one(".prd-discount")
            or card.select_one(".sale-rate")
        )
        discount_rate: float | None = None
        if rate_el:
            discount_rate = _parse_rate(rate_el.get_text())
        # 할인율 직접 표시 없을 때 계산
        if discount_rate is None and original_price and sale_price and original_price > 0:
            discount_rate = round((1 - sale_price / original_price) * 100, 1)

        # 프로모션 reason
        reason = _extract_promo_reason(card)

        # confidence 결정
        if original_price is not None and sale_price is not None:
            confidence = 0.8
        elif original_price is not None or sale_price is not None:
            confidence = 0.5
        else:
            confidence = 0.0

        return ScrapedEvent(
            product_name=product_name,
            brand=brand,
            original_price=original_price,
            sale_price=sale_price,
            discount_rate=discount_rate,
            currency="KRW",
            reason=reason,
            source_url=source_url,
            confidence=confidence,
            raw_text=raw_text,
        )
    except Exception as exc:  # pylint: disable=broad-except
        _logger.warning("아모레몰 카드 파싱 실패: %s | raw=%s", exc, raw_text[:200])
        return ScrapedEvent(
            product_name=query,
            confidence=0.0,
            raw_text=raw_text,
        )


class AmoremallScraper(BaseScraper):
    """아모레몰(amoremall.com) 공홈 검색 스크래퍼 — SPA(Playwright + BeautifulSoup)."""

    PLATFORM_NAME = "아모레몰"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 2.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        url = SEARCH_URL.format(query=quote_plus(query))
        try:
            async with async_playwright() as pw:
                launch_kwargs: dict[str, object] = {
                    "headless": True,
                    "executable_path": "/usr/bin/google-chrome-stable",
                    "args": ["--no-sandbox", "--disable-dev-shm-usage"],
                }
                proxy_config = playwright_proxy()
                if proxy_config:
                    launch_kwargs["proxy"] = proxy_config

                browser = await pw.chromium.launch(**launch_kwargs)  # type: ignore[arg-type]
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()
                await self._wait_rate_limit()

                await page.goto(url, wait_until="domcontentloaded", timeout=30000)

                # SPA 렌더링 대기: 상품 카드 셀렉터 후보 순서대로 시도
                matched_selector: str | None = None
                for selector in _CARD_SELECTORS:
                    try:
                        await page.wait_for_selector(selector, timeout=8000)
                        matched_selector = selector
                        break
                    except Exception:
                        continue

                if matched_selector is None:
                    _logger.warning(
                        "아모레몰: selector 미매칭 — 상품 카드를 찾지 못했습니다. url=%s", url
                    )
                    await browser.close()
                    return []

                html = await page.content()
                await browser.close()

            soup = BeautifulSoup(html, "html.parser")
            cards = soup.select(matched_selector)

            if not cards:
                _logger.warning("아모레몰: 파싱된 카드 0건. selector=%s", matched_selector)
                return []

            for card in cards[:10]:  # 최대 10개
                event = _parse_card(card, url, query)
                events.append(event)

        except Exception as exc:
            _logger.warning("아모레몰 scrape 실패: %s", exc)
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )
        return events
