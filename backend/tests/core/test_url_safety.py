"""Tests for URL scheme filtering helpers."""
from app.core.url_safety import safe_url


def test_safe_url_allows_http_and_https() -> None:
    assert safe_url("https://example.com/product") == "https://example.com/product"
    assert safe_url("http://example.com/product") == "http://example.com/product"


def test_safe_url_rejects_unsafe_schemes() -> None:
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("data:text/html,<script>alert(1)</script>") is None


def test_safe_url_rejects_empty_or_relative_urls() -> None:
    assert safe_url(None) is None
    assert safe_url("") is None
    assert safe_url("/relative/path") is None
