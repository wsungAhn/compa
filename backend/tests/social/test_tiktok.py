"""TikTok collector unit tests."""
from datetime import datetime
from typing import Any

from app.social.tiktok import TikTokCollector, parse_response


def test_collector_platform_attrs() -> None:
    """Test collector has correct platform configuration."""
    collector = TikTokCollector()
    assert collector.PLATFORM == "tiktok"
    assert collector.RATE_LIMIT_SEC == 1.0


def test_parse_response_empty_dict() -> None:
    """Test parsing empty response."""
    data: dict[str, Any] = {}
    posts = parse_response(data)
    assert posts == []


def test_parse_response_empty_data() -> None:
    """Test parsing response with no data."""
    data: dict[str, Any] = {"data": {}}
    posts = parse_response(data)
    assert posts == []


def test_parse_response_empty_videos() -> None:
    """Test parsing response with empty videos list."""
    data: dict[str, Any] = {"data": {"videos": []}}
    posts = parse_response(data)
    assert posts == []


def test_parse_response_single_video() -> None:
    """Test parsing single TikTok video."""
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7123456789",
                    "video_description": "Amazing skincare routine with this product!",
                    "share_url": "https://www.tiktok.com/@user/video/7123456789",
                    "create_time": 1718462400,
                }
            ]
        }
    }
    posts = parse_response(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.platform == "tiktok"
    assert post.content == "Amazing skincare routine with this product!"
    assert post.post_url == "https://www.tiktok.com/@user/video/7123456789"
    assert post.posted_at is not None
    assert isinstance(post.posted_at, datetime)


def test_parse_response_no_description() -> None:
    """Test that videos without description are skipped."""
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7123456789",
                    "video_description": "",
                    "share_url": "https://www.tiktok.com/@user/video/7123456789",
                    "create_time": 1718462400,
                }
            ]
        }
    }
    posts = parse_response(data)
    assert posts == []


def test_parse_response_missing_share_url() -> None:
    """Test parsing video without share_url (fallback to video ID)."""
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7123456789",
                    "video_description": "Great product!",
                    "create_time": 1718462400,
                }
            ]
        }
    }
    posts = parse_response(data)

    assert len(posts) == 1
    post = posts[0]
    assert "7123456789" in (post.post_url or "")
    assert post.post_url is not None


def test_parse_response_invalid_create_time() -> None:
    """Test parsing video with invalid create_time."""
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7123456789",
                    "video_description": "Great product!",
                    "share_url": "https://www.tiktok.com/@user/video/7123456789",
                    "create_time": "invalid",
                }
            ]
        }
    }
    posts = parse_response(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_response_missing_create_time() -> None:
    """Test parsing video without create_time."""
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7123456789",
                    "video_description": "Great product!",
                    "share_url": "https://www.tiktok.com/@user/video/7123456789",
                }
            ]
        }
    }
    posts = parse_response(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_response_multiple_videos() -> None:
    """Test parsing multiple TikTok videos."""
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7111",
                    "video_description": "Product A review",
                    "share_url": "https://www.tiktok.com/@user/video/7111",
                    "create_time": 1718462400,
                },
                {
                    "id": "7222",
                    "video_description": "Product B haul",
                    "share_url": "https://www.tiktok.com/@user/video/7222",
                    "create_time": 1718375000,
                },
            ]
        }
    }
    posts = parse_response(data)

    assert len(posts) == 2
    assert posts[0].content == "Product A review"
    assert posts[1].content == "Product B haul"


def test_parse_response_timestamp_parsing() -> None:
    """Test correct parsing of epoch timestamp to datetime."""
    # 1718462400 = 2024-06-15 12:00:00 UTC
    data: dict[str, Any] = {
        "data": {
            "videos": [
                {
                    "id": "7123456789",
                    "video_description": "Great product!",
                    "share_url": "https://www.tiktok.com/@user/video/7123456789",
                    "create_time": 1718462400,
                }
            ]
        }
    }
    posts = parse_response(data)

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is not None
    assert post.posted_at.year == 2024
    assert post.posted_at.month == 6
    assert post.posted_at.day == 15
