import re
from datetime import date, datetime

from playwright.async_api import async_playwright

from app.scrapers.base import BaseScraper, ScrapedEvent

SEARCH_URL = "https://www.oliveyoung.co.kr/store/search/getSearchMain.do?query={query}"
SALE_URL = "https://www.oliveyoung.co.kr/store/main/getBrandShopDetail.do"

_PRICE_RE = re.compile(r"[\d,]+")
_DATE_RE = re.compile(r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})")


def _parse_price(text: str) -> float | None:
    m = _PRICE_RE.search(text.replace(",", ""))
    return float(m.group()) if m else None


def _parse_date(text: str) -> date | None:
    m = _DATE_RE.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


class OliveYoungScraper(BaseScraper):
    PLATFORM_NAME = "Olive Young"
    COUNTRY = "KR"
    RATE_LIMIT_SEC = 1.0

    async def scrape(self, query: str) -> list[ScrapedEvent]:
        events: list[ScrapedEvent] = []
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(
                    headless=True,
                    executable_path="/usr/bin/google-chrome-stable",
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    )
                )
                page = await context.new_page()
                await self._wait_rate_limit()

                url = SEARCH_URL.format(query=query)
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)

                # 검색 결과에서 상품 목록 파싱
                items = await page.query_selector_all(".prd-info-detail")
                for item in items[:5]:  # 최대 5개
                    try:
                        name_el = await item.query_selector(".prd-name")
                        name = (await name_el.inner_text()).strip() if name_el else query

                        brand_el = await item.query_selector(".tx-brand")
                        brand = (await brand_el.inner_text()).strip() if brand_el else None

                        # 정가
                        original_el = await item.query_selector(".tx-org")
                        original_text = (await original_el.inner_text()) if original_el else ""
                        original_price = _parse_price(original_text)

                        # 할인가
                        sale_el = await item.query_selector(".tx-cur")
                        sale_text = (await sale_el.inner_text()) if sale_el else ""
                        sale_price = _parse_price(sale_text)

                        # 할인율
                        rate_el = await item.query_selector(".tx-prd")
                        rate_text = (await rate_el.inner_text()) if rate_el else ""
                        rate_m = re.search(r"(\d+)%", rate_text)
                        discount_rate = float(rate_m.group(1)) if rate_m else None

                        # 할인율 계산 (직접 표시 안 될 때)
                        if discount_rate is None and original_price and sale_price and original_price > 0:
                            discount_rate = round((1 - sale_price / original_price) * 100, 1)

                        raw_text = await item.inner_text()

                        if sale_price and original_price and sale_price < original_price:
                            events.append(
                                ScrapedEvent(
                                    product_name=name,
                                    brand=brand,
                                    original_price=original_price,
                                    sale_price=sale_price,
                                    discount_rate=discount_rate,
                                    currency="KRW",
                                    event_name="올리브영 할인",
                                    source_url=url,
                                    confidence=0.8,
                                    raw_text=raw_text,
                                )
                            )
                    except Exception:
                        events.append(
                            ScrapedEvent(
                                product_name=query,
                                confidence=0.0,
                                raw_text="파싱 오류",
                            )
                        )

                # 기획전 페이지 별도 수집
                await self._wait_rate_limit()
                try:
                    events += await self._scrape_sale_events(page, query)
                except Exception:
                    pass

                await browser.close()
        except Exception as exc:
            events.append(
                ScrapedEvent(
                    product_name=query,
                    confidence=0.0,
                    raw_text=str(exc),
                )
            )
        return events

    async def _scrape_sale_events(self, page, query: str) -> list[ScrapedEvent]:  # type: ignore[no-untyped-def]
        events: list[ScrapedEvent] = []
        sale_page_url = "https://www.oliveyoung.co.kr/store/main/getOliveEvent.do"
        await page.goto(sale_page_url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(1500)

        banners = await page.query_selector_all(".event-list li")
        for banner in banners[:10]:
            try:
                title_el = await banner.query_selector(".tit")
                title = (await title_el.inner_text()).strip() if title_el else ""

                if query.lower() not in title.lower() and not any(
                    kw in title for kw in ["세일", "할인", "기획전", "특가"]
                ):
                    continue

                date_el = await banner.query_selector(".date")
                date_text = (await date_el.inner_text()) if date_el else ""
                dates = _DATE_RE.findall(date_text)

                start_date: date | None = None
                end_date: date | None = None
                if len(dates) >= 2:
                    try:
                        start_date = date(int(dates[0][0]), int(dates[0][1]), int(dates[0][2]))
                        end_date = date(int(dates[1][0]), int(dates[1][1]), int(dates[1][2]))
                    except ValueError:
                        pass

                raw_text = await banner.inner_text()
                events.append(
                    ScrapedEvent(
                        product_name=query,
                        event_name=title or "올리브영 기획전",
                        start_date=start_date,
                        end_date=end_date,
                        currency="KRW",
                        source_url=sale_page_url,
                        confidence=0.6,
                        raw_text=raw_text,
                    )
                )
            except Exception:
                pass
        return events
