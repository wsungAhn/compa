"""Settings.allowed_origins 파서 단위 테스트."""
import pytest
from app.core.config import Settings


def test_single_origin() -> None:
    s = Settings(allowed_origins="http://localhost:5173")  # type: ignore[call-arg]
    assert s.allowed_origins == ["http://localhost:5173"]


def test_comma_separated_no_spaces() -> None:
    s = Settings(allowed_origins="http://localhost:5173,https://example.com")  # type: ignore[call-arg]
    assert s.allowed_origins == ["http://localhost:5173", "https://example.com"]


def test_comma_separated_with_spaces() -> None:
    s = Settings(allowed_origins="http://localhost:5173 , https://example.com , https://api.example.com")  # type: ignore[call-arg]
    assert s.allowed_origins == [
        "http://localhost:5173",
        "https://example.com",
        "https://api.example.com",
    ]


def test_list_passthrough() -> None:
    s = Settings(allowed_origins=["http://a.com", "http://b.com"])  # type: ignore[call-arg]
    assert s.allowed_origins == ["http://a.com", "http://b.com"]


def test_empty_entries_ignored() -> None:
    s = Settings(allowed_origins="http://localhost:5173,,https://example.com,")  # type: ignore[call-arg]
    assert "" not in s.allowed_origins
    assert len(s.allowed_origins) == 2
