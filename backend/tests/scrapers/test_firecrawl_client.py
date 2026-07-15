"""firecrawl-local client availability tests."""
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scrapers import firecrawl_client


@pytest.mark.asyncio
async def test_firecrawl_scrape_logs_when_sdk_missing(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(firecrawl_client, "AsyncFirecrawlClient", None)

    with caplog.at_level(logging.WARNING):
        products = await firecrawl_client.firecrawl_scrape(
            "http://example.com",
            "extract products",
        )

    assert products == []
    assert "SDK is not installed" in caplog.text


@pytest.mark.asyncio
async def test_get_firecrawl_status_reports_missing_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(firecrawl_client, "AsyncFirecrawlClient", None)

    status = await firecrawl_client.get_firecrawl_status()

    assert status["sdk_installed"] is False
    assert status["available"] is False
    assert status["error"] == "firecrawl-local SDK not installed"


@pytest.mark.asyncio
async def test_get_firecrawl_status_reports_server_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {"version": "0.12.0"}
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value.get.return_value = mock_response
    monkeypatch.setattr(firecrawl_client, "AsyncFirecrawlClient", object)
    monkeypatch.setattr(firecrawl_client.httpx, "AsyncClient", MagicMock(return_value=mock_client))

    status = await firecrawl_client.get_firecrawl_status()

    assert status["sdk_installed"] is True
    assert status["available"] is True
    assert status["version"] == "0.12.0"
