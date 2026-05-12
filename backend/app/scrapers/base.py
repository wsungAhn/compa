import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class ScrapedEvent:
    product_name: str
    brand: str | None = None
    original_price: float | None = None
    sale_price: float | None = None
    discount_rate: float | None = None
    currency: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    event_name: str | None = None
    reason: str | None = None
    source_url: str | None = None
    confidence: float = 1.0
    raw_text: str | None = None


class BaseScraper(ABC):
    RATE_LIMIT_SEC: float = 1.0
    PLATFORM_NAME: str = ""
    COUNTRY: str = ""

    def __init__(self) -> None:
        self._last_request: float = 0.0

    async def _wait_rate_limit(self) -> None:
        import time
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.RATE_LIMIT_SEC:
            await asyncio.sleep(self.RATE_LIMIT_SEC - elapsed)
        import time as t
        self._last_request = t.monotonic()

    @abstractmethod
    async def scrape(self, query: str) -> list[ScrapedEvent]:
        """제품명으로 할인 행사 데이터를 수집하여 반환."""
        ...
