"""Proxy management utilities for scraping operations."""
from app.core.config import settings


def get_proxy_url() -> str | None:
    """Get proxy URL from settings.

    Returns:
        Proxy URL string or None if not configured.
    """
    url = settings.proxy_pool_url.strip() if settings.proxy_pool_url else ""
    return url if url else None


def httpx_proxy() -> str | None:
    """Get proxy URL formatted for httpx.AsyncClient.

    Returns:
        Proxy URL string or None if not configured.
    """
    return get_proxy_url()


def playwright_proxy() -> dict[str, str] | None:
    """Get proxy configuration formatted for Playwright.

    Returns:
        Dictionary with 'server' key or None if not configured.
    """
    url = get_proxy_url()
    return {"server": url} if url else None
