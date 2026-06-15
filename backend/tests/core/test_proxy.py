"""Proxy module unit tests."""
from unittest.mock import patch

from app.core.proxy import get_proxy_url, httpx_proxy, playwright_proxy


def test_get_proxy_url_with_value() -> None:
    """Test get_proxy_url returns proxy URL when configured."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = "http://proxy.example.com:8080"

        result = get_proxy_url()

        assert result == "http://proxy.example.com:8080"


def test_get_proxy_url_empty_string() -> None:
    """Test get_proxy_url returns None for empty string."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = ""

        result = get_proxy_url()

        assert result is None


def test_get_proxy_url_whitespace_only() -> None:
    """Test get_proxy_url returns None for whitespace-only string."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = "   "

        result = get_proxy_url()

        assert result is None


def test_httpx_proxy_with_value() -> None:
    """Test httpx_proxy returns proxy URL when configured."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = "http://httpx-proxy:9090"

        result = httpx_proxy()

        assert result == "http://httpx-proxy:9090"


def test_httpx_proxy_none() -> None:
    """Test httpx_proxy returns None when not configured."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = ""

        result = httpx_proxy()

        assert result is None


def test_playwright_proxy_with_value() -> None:
    """Test playwright_proxy returns dict with server key when configured."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = "http://pw-proxy:3000"

        result = playwright_proxy()

        assert result == {"server": "http://pw-proxy:3000"}


def test_playwright_proxy_none() -> None:
    """Test playwright_proxy returns None when not configured."""
    with patch("app.core.proxy.settings") as mock_settings:
        mock_settings.proxy_pool_url = ""

        result = playwright_proxy()

        assert result is None
