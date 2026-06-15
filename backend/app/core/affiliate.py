"""Affiliate link conversion utilities."""
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse

from app.core.config import settings


def to_affiliate_url(source_url: str | None, platform_name: str) -> str | None:
    """Convert a product URL to an affiliate link if applicable.

    Args:
        source_url: Original product URL
        platform_name: Platform name (e.g., "Amazon US", "쿠팡", "Rakuten")

    Returns:
        Affiliate URL if applicable, otherwise unchanged source_url or None
    """
    if not source_url:
        return None

    if platform_name == "Amazon US" and settings.amazon_partner_tag:
        if "amazon.com" not in source_url:
            return source_url
        # Parse URL to check/append tag param
        parsed = urlparse(source_url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        # If tag already exists, return unchanged
        if "tag" in query_params:
            return source_url
        # Add tag parameter
        query_params["tag"] = [settings.amazon_partner_tag]
        new_query = urlencode(query_params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    elif platform_name == "쿠팡" and settings.coupang_partner_id:
        if "coupang.com" not in source_url:
            return source_url
        # TODO: Real Coupang Partners uses a link-generation API; this is the documented lptag shortcut
        parsed = urlparse(source_url)
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        # If lptag already exists, return unchanged
        if "lptag" in query_params:
            return source_url
        # Add lptag parameter
        query_params["lptag"] = [settings.coupang_partner_id]
        new_query = urlencode(query_params, doseq=True)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

    elif platform_name == "Rakuten" and settings.rakuten_affiliate_id:
        if "rakuten.co.jp" not in source_url:
            return source_url
        # Wrap with Rakuten affiliate URL
        encoded_url = quote(source_url, safe="")
        return f"https://hb.afl.rakuten.co.jp/hgc/{settings.rakuten_affiliate_id}/?pc={encoded_url}"

    return source_url
