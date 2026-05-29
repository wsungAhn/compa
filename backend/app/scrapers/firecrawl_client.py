# firecrawl-local SDK 래퍼 — AsyncFirecrawlClient 기반
import logging

from firecrawl_local import AsyncFirecrawlClient, FirecrawlError

from app.core.config import settings

_logger = logging.getLogger(__name__)

_EXTRACT_SCHEMA = {
    "products": [
        {
            "product_name": "string (required)",
            "brand": "string or null",
            "original_price": "number or null",
            "sale_price": "number or null",
            "discount_rate": "number or null (percentage 0-100)",
            "currency": "KRW | USD | JPY | CNY | null",
            "start_date": "YYYY-MM-DD or null",
            "end_date": "YYYY-MM-DD or null",
            "event_name": "string or null",
            "reason": "string or null",
            "confidence": "float 0.0-1.0",
        }
    ]
}


async def firecrawl_scrape(
    url: str,
    extract_prompt: str,
    wait_for: str | None = None,
    timeout: int = 30000,
    remove_selectors: list[str] | None = None,
) -> list[dict]:
    """firecrawl-local SDK로 스크래핑. 추출된 products 리스트 반환.

    실패 시 빈 리스트 반환 (예외 전파 금지).
    """
    try:
        async with AsyncFirecrawlClient(
            base_url=settings.firecrawl_url,
            timeout=timeout / 1000 + 60,
        ) as client:
            data = await client.scrape(
                url,
                wait_for=wait_for,
                timeout=timeout,
                remove_selectors=remove_selectors or [],
                extract={
                    "prompt": extract_prompt,
                    "output_schema": _EXTRACT_SCHEMA,
                    "provider": settings.firecrawl_extract_provider,
                },
            )
        extracted = data.get("extracted") or {}
        return extracted.get("products", [])

    except FirecrawlError as e:
        _logger.warning(f"firecrawl_scrape failed for {url}: {e}")
        return []
    except Exception as e:
        _logger.warning(f"firecrawl_scrape unexpected error for {url}: {e}")
        return []
