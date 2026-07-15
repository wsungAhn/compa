"""URL safety helpers for untrusted scraper and social links."""
from urllib.parse import urlparse


def safe_url(url: str | None) -> str | None:
    """Return URL only when it uses an allowed web scheme."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return None
    if not parsed.netloc:
        return None
    return url
