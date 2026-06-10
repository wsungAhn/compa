"""Base class for social media collectors."""
import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SocialPostData:
    """Standardized social media post data."""

    platform: str
    post_url: str | None
    content: str
    posted_at: datetime | None = None


class BaseSocialCollector(ABC):
    """Abstract base class for social media collectors."""

    PLATFORM: str = ""
    RATE_LIMIT_SEC: float = 1.0

    def __init__(self) -> None:
        self._last_request: float = 0.0

    async def _wait_rate_limit(self) -> None:
        """Wait to respect rate limit (1 req/sec or custom)."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.RATE_LIMIT_SEC:
            await asyncio.sleep(self.RATE_LIMIT_SEC - elapsed)
        self._last_request = time.monotonic()

    @abstractmethod
    async def collect(self, query: str) -> list[SocialPostData]:
        """Collect social posts for a given query."""
        ...
