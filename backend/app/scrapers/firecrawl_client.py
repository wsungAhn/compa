# firecrawl-local SDK 래퍼 — AsyncFirecrawlClient 기반
import logging

import httpx

try:
    from firecrawl_local import AsyncFirecrawlClient, FirecrawlError
except ImportError:  # firecrawl-local SDK 미설치 환경 (CI 등)
    AsyncFirecrawlClient = None

    class FirecrawlError(Exception):  # type: ignore[no-redef]
        pass

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


async def get_firecrawl_status() -> dict[str, object]:
    """Return SDK/server availability for /health."""
    status: dict[str, object] = {
        "sdk_installed": AsyncFirecrawlClient is not None,
        "available": False,
        "url": settings.firecrawl_url,
        "version": None,
        "error": None,
    }
    if AsyncFirecrawlClient is None:
        status["error"] = "firecrawl-local SDK not installed"
        return status

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{settings.firecrawl_url.rstrip('/')}/health")
        response.raise_for_status()
        data = response.json()
        status["available"] = True
        if isinstance(data, dict):
            status["version"] = data.get("version")
        return status
    except Exception as exc:
        status["error"] = f"{type(exc).__name__}: {exc}"
        return status


async def firecrawl_scrape(
    url: str,
    extract_prompt: str,
    wait_for: str | None = None,
    timeout: int = 30000,
    remove_selectors: list[str] | None = None,
) -> list[dict[str, object]]:
    """firecrawl-local SDK로 스크래핑. 추출된 products 리스트 반환."""
    if AsyncFirecrawlClient is None:
        _logger.warning(
            "firecrawl-local SDK is not installed; install backend/requirements-firecrawl-local.txt"
        )
        return []
    try:
        async with AsyncFirecrawlClient(
            base_url=settings.firecrawl_url,
            timeout=timeout / 1000 + 60,
        ) as client:
            data: dict[str, object] = await client.scrape(
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
        extracted: dict[str, object] = (data.get("extracted") or {})  # type: ignore[assignment]
        products: list[dict[str, object]] = extracted.get("products", [])  # type: ignore[assignment]
        return products

    except FirecrawlError as e:
        _logger.warning(f"firecrawl_scrape failed for {url}: {e}")
        return []
    except Exception as e:
        _logger.warning(f"firecrawl_scrape unexpected error for {url}: {e}")
        return []
