"""Naver Blog collector unit tests."""
from typing import Any

from app.social.naver_blog import NaverBlogCollector, parse_response


def test_collector_platform_attrs() -> None:
    """Test collector has correct platform configuration."""
    collector = NaverBlogCollector()
    assert collector.PLATFORM == "naver_blog"
    assert collector.RATE_LIMIT_SEC == 1.0


def test_parse_response_empty_dict() -> None:
    """Test parsing empty response."""
    data: dict[str, Any] = {}
    posts = parse_response(data, "naver_blog")
    assert posts == []


def test_parse_response_empty_items() -> None:
    """Test parsing response with no items."""
    data: dict[str, Any] = {"items": []}
    posts = parse_response(data, "naver_blog")
    assert posts == []


def test_parse_response_single_item() -> None:
    """Test parsing single blog post."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "클렌징 폼 사용 후기",
                "description": "정말 좋은 제품입니다.",
                "link": "https://blog.naver.com/user/12345",
                "postdate": "20240615",
            }
        ]
    }
    posts = parse_response(data, "naver_blog")

    assert len(posts) == 1
    post = posts[0]
    assert post.platform == "naver_blog"
    assert post.post_url == "https://blog.naver.com/user/12345"
    assert post.content == "클렌징 폼 사용 후기 정말 좋은 제품입니다."
    assert post.posted_at is not None
    assert post.posted_at.year == 2024
    assert post.posted_at.month == 6
    assert post.posted_at.day == 15


def test_parse_response_with_html_tags() -> None:
    """Test parsing post with <b> HTML tags."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "<b>클렌징</b> 폼 추천",
                "description": "이 <b>제품</b>은 최고입니다",
                "link": "https://blog.naver.com/user/12345",
                "postdate": "20240615",
            }
        ]
    }
    posts = parse_response(data, "naver_blog")

    assert len(posts) == 1
    post = posts[0]
    # HTML tags should be stripped
    assert "<b>" not in post.content
    assert "</b>" not in post.content
    assert "클렌징" in post.content
    assert "제품" in post.content


def test_parse_response_missing_postdate() -> None:
    """Test parsing post without postdate."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "제품 후기",
                "description": "좋습니다",
                "link": "https://blog.naver.com/user/12345",
            }
        ]
    }
    posts = parse_response(data, "naver_blog")

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_response_invalid_postdate() -> None:
    """Test parsing post with invalid postdate format."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "제품 후기",
                "description": "좋습니다",
                "link": "https://blog.naver.com/user/12345",
                "postdate": "invalid",
            }
        ]
    }
    posts = parse_response(data, "naver_blog")

    assert len(posts) == 1
    post = posts[0]
    assert post.posted_at is None


def test_parse_response_missing_content() -> None:
    """Test that items without content are skipped."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "",
                "description": "",
                "link": "https://blog.naver.com/user/12345",
                "postdate": "20240615",
            }
        ]
    }
    posts = parse_response(data, "naver_blog")
    assert posts == []


def test_parse_response_multiple_items() -> None:
    """Test parsing multiple blog posts."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "제품1 후기",
                "description": "좋습니다",
                "link": "https://blog.naver.com/user/1",
                "postdate": "20240615",
            },
            {
                "title": "제품2 후기",
                "description": "최고입니다",
                "link": "https://blog.naver.com/user/2",
                "postdate": "20240610",
            },
        ]
    }
    posts = parse_response(data, "naver_blog")

    assert len(posts) == 2
    assert posts[0].content == "제품1 후기 좋습니다"
    assert posts[1].content == "제품2 후기 최고입니다"


def test_parse_response_missing_link() -> None:
    """Test parsing post without link URL."""
    data: dict[str, Any] = {
        "items": [
            {
                "title": "제품 후기",
                "description": "좋습니다",
                "postdate": "20240615",
            }
        ]
    }
    posts = parse_response(data, "naver_blog")

    assert len(posts) == 1
    post = posts[0]
    assert post.post_url is None
