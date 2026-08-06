import asyncio
import os
import pathlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

_LINUX_CHROME = "/usr/bin/google-chrome-stable"


def chrome_launch_kwargs() -> dict[str, object]:
    """Playwright launch kwargs pointing at a real Chrome.

    Ubuntu needs the explicit path (the bundled Chromium doesn't support 26.04),
    but that path doesn't exist on macOS/Windows — there Playwright's `channel`
    finds the installed Chrome. CHROME_PATH overrides both.
    """
    kwargs: dict[str, object] = {
        "headless": True,
        "args": ["--no-sandbox", "--disable-dev-shm-usage"],
    }
    override = os.environ.get("CHROME_PATH")
    if override:
        kwargs["executable_path"] = override
    elif pathlib.Path(_LINUX_CHROME).exists():
        kwargs["executable_path"] = _LINUX_CHROME
    else:
        kwargs["channel"] = "chrome"
    return kwargs


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
    event_type: str | None = None  # "regular" | "surprise" | None
    # ml로 정규화한 용량. 크로스 통화 매칭의 급소 — 미국은 oz, 일본은 ml로 표기해
    # 정규화 없이는 정답 쌍까지 탈락한다(실측 0/10).
    size_ml: float | None = None


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
