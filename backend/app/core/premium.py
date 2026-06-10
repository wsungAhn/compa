"""Premium tier authentication and gating utilities."""
from fastapi import Header

from app.core.config import settings


def parse_premium_keys(raw: str) -> set[str]:
    """Parse comma-separated API keys for premium tier.

    Args:
        raw: Comma-separated string of API keys (may include whitespace)

    Returns:
        Set of valid premium API keys (stripped of whitespace, empty strings excluded)
    """
    if not raw:
        return set()
    keys = {key.strip() for key in raw.split(",") if key.strip()}
    return keys


def is_premium_key(key: str | None) -> bool:
    """Check if a given API key is valid for premium tier.

    Args:
        key: API key from request header (or None)

    Returns:
        True if key is in the configured premium API keys, False otherwise
    """
    if not key:
        return False
    valid_keys = parse_premium_keys(settings.premium_api_keys)
    return key in valid_keys


async def premium_dep(x_premium_key: str | None = Header(default=None)) -> bool:
    """FastAPI dependency to extract and validate premium status from header.

    Args:
        x_premium_key: Value of X-Premium-Key header (if present)

    Returns:
        True if key is valid premium key, False otherwise
    """
    return is_premium_key(x_premium_key)
