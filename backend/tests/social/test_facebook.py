"""Facebook collector unit tests."""
from datetime import datetime
from typing import Any

from app.social.facebook import FacebookCollector, parse_posts


def test_collector_platform_attrs() -> None:
    """Test collector has correct platform configuration."""
    collector = FacebookCollector()
    assert collector.PLATFORM == "facebook"
    assert collector.RATE_LIMIT_SEC == 1.0


def test_parse_posts_empty_dict() -> None:
    """Test parsing empty response."""
    data: dict[str, Any] = {}
    posts = parse_posts(data)
    assert posts == []


def test_parse_posts_empty_data() -> None:
    """Test parsing response with no data."""
    data: dict[str, Any] = {"data": []}
    posts = parse_posts(data)
    assert posts == []


def test_parse_posts_single_page() -> None:
    """Test parsing single page result."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "Beauty Products Store",
                "link": "https://www.facebook.com/beautystoreofficial",
                "updated_time": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.platform == "facebook"
    assert post.content == "Beauty Products Store"
    assert post.post_url == "https://www.facebook.com/beautystoreofficial"
    assert post.posted_at is not None
    assert isinstance(post.posted_at, datetime)


def test_parse_posts_with_message() -> None:
    """Test parsing page with message instead of name."""
    data: dict[str, Any] = {
        "data": [
            {
                "message": "Check out our new skincare line!",
                "link": "https://www.facebook.com/page/post/123",
                "updated_time": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.content == "Check out our new skincare line!"


def test_parse_posts_no_content() -> None:
    """Test that pages without name or message are skipped."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "",
                "link": "https://www.facebook.com/page",
                "updated_time": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_posts(data)
    assert posts == []


def test_parse_posts_missing_link() -> None:
    """Test parsing page without link."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "Beauty Store",
                "updated_time": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.post_url is None


def test_parse_posts_invalid_timestamp() -> None:
    """Test parsing page with invalid timestamp."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "Beauty Store",
                "link": "https://www.facebook.com/page",
                "updated_time": "invalid-date",
            }
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_posts_missing_timestamp() -> None:
    """Test parsing page without timestamp."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "Beauty Store",
                "link": "https://www.facebook.com/page",
            }
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_posts_multiple_pages() -> None:
    """Test parsing multiple page results."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "Store A",
                "link": "https://www.facebook.com/store-a",
                "updated_time": "2024-06-15T10:00:00Z",
            },
            {
                "name": "Store B",
                "link": "https://www.facebook.com/store-b",
                "updated_time": "2024-06-14T14:00:00Z",
            },
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 2
    assert posts[0].content == "Store A"
    assert posts[1].content == "Store B"


def test_parse_posts_timestamp_with_z() -> None:
    """Test parsing timestamp with Z suffix."""
    data: dict[str, Any] = {
        "data": [
            {
                "name": "Beauty Store",
                "link": "https://www.facebook.com/page",
                "updated_time": "2024-06-15T10:30:00Z",
            }
        ]
    }
    posts = parse_posts(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is not None
    assert post.posted_at.year == 2024
    assert post.posted_at.month == 6
    assert post.posted_at.day == 15
