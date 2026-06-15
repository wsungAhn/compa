"""Instagram collector unit tests."""
from datetime import datetime
from typing import Any

from app.social.instagram import InstagramCollector, parse_media


def test_collector_platform_attrs() -> None:
    """Test collector has correct platform configuration."""
    collector = InstagramCollector()
    assert collector.PLATFORM == "instagram"
    assert collector.RATE_LIMIT_SEC == 1.0


def test_parse_media_empty_dict() -> None:
    """Test parsing empty response."""
    data: dict[str, Any] = {}
    posts = parse_media(data)
    assert posts == []


def test_parse_media_empty_data() -> None:
    """Test parsing response with no data."""
    data: dict[str, Any] = {"data": []}
    posts = parse_media(data)
    assert posts == []


def test_parse_media_single_post() -> None:
    """Test parsing single Instagram media."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "123456789",
                "caption": "Amazing skincare product! 💆",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "timestamp": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_media(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.platform == "instagram"
    assert post.content == "Amazing skincare product! 💆"
    assert post.post_url == "https://www.instagram.com/p/ABC123/"
    assert post.posted_at is not None
    assert isinstance(post.posted_at, datetime)


def test_parse_media_no_caption() -> None:
    """Test that media without caption are skipped."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "123456789",
                "caption": "",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "timestamp": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_media(data)
    assert posts == []


def test_parse_media_missing_permalink() -> None:
    """Test parsing media without permalink."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "123456789",
                "caption": "Great product!",
                "timestamp": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_media(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.post_url is None


def test_parse_media_invalid_timestamp() -> None:
    """Test parsing media with invalid timestamp."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "123456789",
                "caption": "Great product!",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "timestamp": "invalid-date",
            }
        ]
    }
    posts = parse_media(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_media_missing_timestamp() -> None:
    """Test parsing media without timestamp."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "123456789",
                "caption": "Great product!",
                "permalink": "https://www.instagram.com/p/ABC123/",
            }
        ]
    }
    posts = parse_media(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_media_multiple_posts() -> None:
    """Test parsing multiple Instagram media."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "111",
                "caption": "Product A review",
                "permalink": "https://www.instagram.com/p/A/",
                "timestamp": "2024-06-15T10:00:00Z",
            },
            {
                "id": "222",
                "caption": "Product B unboxing",
                "permalink": "https://www.instagram.com/p/B/",
                "timestamp": "2024-06-14T14:00:00Z",
            },
        ]
    }
    posts = parse_media(data)

    assert len(posts) == 2
    assert posts[0].content == "Product A review"
    assert posts[1].content == "Product B unboxing"


def test_parse_media_timestamp_with_z() -> None:
    """Test parsing media with Z-suffixed ISO timestamp."""
    data: dict[str, Any] = {
        "data": [
            {
                "id": "123456789",
                "caption": "Great product!",
                "permalink": "https://www.instagram.com/p/ABC123/",
                "timestamp": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_media(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is not None
    assert post.posted_at.year == 2024
    assert post.posted_at.month == 6
    assert post.posted_at.day == 15
