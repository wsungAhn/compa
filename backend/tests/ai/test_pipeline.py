"""Unit tests for social extraction pipeline."""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import (
    CURRENCY_TO_COUNTRY,
    SOCIAL_PLATFORM_NAME,
    infer_country,
    match_event_to_post,
    process_social_posts,
)


# ============================================================================
# Pure function tests: infer_country
# ============================================================================


class TestInferCountry:
    """Test infer_country pure function."""

    def test_krw_currency_returns_kr(self) -> None:
        """Test KRW currency maps to KR."""
        result = infer_country("KRW", "instagram")
        assert result == "KR"

    def test_usd_currency_returns_us(self) -> None:
        """Test USD currency maps to US."""
        result = infer_country("USD", "instagram")
        assert result == "US"

    def test_jpy_currency_returns_jp(self) -> None:
        """Test JPY currency maps to JP."""
        result = infer_country("JPY", "tiktok")
        assert result == "JP"

    def test_cny_currency_returns_cn(self) -> None:
        """Test CNY currency maps to CN."""
        result = infer_country("CNY", "xiaohongshu")
        assert result == "CN"

    def test_naver_blog_without_currency_returns_kr(self) -> None:
        """Test naver_blog platform without currency defaults to KR."""
        result = infer_country(None, "naver_blog")
        assert result == "KR"

    def test_naver_blog_with_currency_prefers_currency(self) -> None:
        """Test that currency takes precedence over platform."""
        result = infer_country("USD", "naver_blog")
        assert result == "US"

    def test_instagram_without_currency_returns_kr(self) -> None:
        """Test instagram without currency defaults to KR."""
        result = infer_country(None, "instagram")
        assert result == "KR"

    def test_tiktok_without_currency_returns_kr(self) -> None:
        """Test tiktok without currency defaults to KR."""
        result = infer_country(None, "tiktok")
        assert result == "KR"

    def test_facebook_without_currency_returns_kr(self) -> None:
        """Test facebook without currency defaults to KR."""
        result = infer_country(None, "facebook")
        assert result == "KR"

    def test_unknown_currency_returns_kr_fallback(self) -> None:
        """Test unknown currency falls back to KR."""
        result = infer_country("UNKNOWN", "instagram")
        assert result == "KR"


# ============================================================================
# Pure function tests: match_event_to_post
# ============================================================================


class TestMatchEventToPost:
    """Test match_event_to_post pure function."""

    def test_product_in_second_post_returns_second_index(self) -> None:
        """Test that product found in second post returns second index."""
        posts = [
            (0, "Some random content about skincare"),
            (1, "Check out this amazing SK-II facial treatment on sale"),
            (2, "Other post"),
        ]
        result = match_event_to_post("SK-II Facial Treatment", posts)
        assert result == 1

    def test_product_in_first_post_returns_first_index(self) -> None:
        """Test that product in first post returns first index."""
        posts = [
            (0, "Amazing Sulwhasoo essence on discount"),
            (1, "Other content"),
        ]
        result = match_event_to_post("Sulwhasoo Essence", posts)
        assert result == 0

    def test_case_insensitive_matching(self) -> None:
        """Test product matching is case-insensitive."""
        posts = [
            (0, "Check out this SK-II Facial Treatment"),
        ]
        result = match_event_to_post("sk-ii facial treatment", posts)
        assert result == 0

    def test_no_match_returns_first_index(self) -> None:
        """Test that no match returns first index."""
        posts = [
            (0, "Random skincare content"),
            (1, "More random content"),
        ]
        result = match_event_to_post("NonExistentProduct", posts)
        assert result == 0

    def test_empty_posts_returns_zero(self) -> None:
        """Test that empty posts list returns 0."""
        posts: list[tuple[int, str]] = []
        result = match_event_to_post("SomeProduct", posts)
        assert result == 0

    def test_partial_name_match_succeeds(self) -> None:
        """Test that partial product name matches."""
        posts = [
            (0, "Amazing SK-II treatment on sale"),
            (1, "Check out Sulwhasoo essence"),
        ]
        result = match_event_to_post("SK-II", posts)
        assert result == 0

    def test_multiple_matches_returns_first_match(self) -> None:
        """Test that when product appears in multiple posts, first is returned."""
        posts = [
            (0, "First post about SK-II"),
            (1, "Another post about SK-II"),
            (2, "Third post"),
        ]
        result = match_event_to_post("SK-II", posts)
        assert result == 0


# ============================================================================
# Mapping dictionary tests
# ============================================================================


class TestCurrencyToCountryMapping:
    """Test CURRENCY_TO_COUNTRY constant."""

    def test_all_four_currencies_mapped(self) -> None:
        """Test that all 4 currencies are mapped."""
        assert "KRW" in CURRENCY_TO_COUNTRY
        assert "USD" in CURRENCY_TO_COUNTRY
        assert "JPY" in CURRENCY_TO_COUNTRY
        assert "CNY" in CURRENCY_TO_COUNTRY

    def test_correct_mappings(self) -> None:
        """Test that currency mappings are correct."""
        assert CURRENCY_TO_COUNTRY["KRW"] == "KR"
        assert CURRENCY_TO_COUNTRY["USD"] == "US"
        assert CURRENCY_TO_COUNTRY["JPY"] == "JP"
        assert CURRENCY_TO_COUNTRY["CNY"] == "CN"


class TestSocialPlatformNameMapping:
    """Test SOCIAL_PLATFORM_NAME constant."""

    def test_all_five_platforms_mapped(self) -> None:
        """Test that all 5 social platforms are mapped."""
        assert "instagram" in SOCIAL_PLATFORM_NAME
        assert "tiktok" in SOCIAL_PLATFORM_NAME
        assert "facebook" in SOCIAL_PLATFORM_NAME
        assert "naver_blog" in SOCIAL_PLATFORM_NAME
        assert "xiaohongshu" in SOCIAL_PLATFORM_NAME

    def test_correct_platform_names(self) -> None:
        """Test that platform names are correct."""
        assert SOCIAL_PLATFORM_NAME["instagram"] == "Instagram"
        assert SOCIAL_PLATFORM_NAME["tiktok"] == "TikTok"
        assert SOCIAL_PLATFORM_NAME["facebook"] == "Facebook"
        assert SOCIAL_PLATFORM_NAME["naver_blog"] == "네이버블로그"
        assert SOCIAL_PLATFORM_NAME["xiaohongshu"] == "小红书"


# ============================================================================
# Database-dependent tests (with mocks)
# ============================================================================


@pytest.mark.asyncio
class TestProcessSocialPosts:
    """Test process_social_posts with mocked database."""

    async def test_returns_zero_when_no_posts(self) -> None:
        """Test that zero events returned when no unprocessed posts exist."""
        mock_db = AsyncMock(spec=AsyncSession)
        mock_cursor_result = MagicMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.all.return_value = []
        mock_cursor_result.scalars.return_value = mock_scalar_result
        mock_db.execute.return_value = mock_cursor_result

        result = await process_social_posts(mock_db, limit=20)

        assert result == 0

    async def test_returns_zero_when_no_api_key(self) -> None:
        """Test that zero events returned when API key is empty."""
        from app.models.social_post import SocialPost

        # Create mock post
        mock_post = MagicMock(spec=SocialPost)
        mock_post.content = "Some content"
        mock_post.processed = False

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cursor_result = MagicMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.all.return_value = [mock_post]
        mock_cursor_result.scalars.return_value = mock_scalar_result
        mock_db.execute.return_value = mock_cursor_result

        with patch("app.ai.pipeline.settings") as mock_settings:
            mock_settings.anthropic_api_key = ""
            result = await process_social_posts(mock_db, limit=20)

        assert result == 0

    async def test_marks_posts_as_processed_even_without_events(self) -> None:
        """Test that posts are marked processed even if no events extracted."""
        from app.models.social_post import SocialPost

        mock_post = MagicMock(spec=SocialPost)
        mock_post.content = "Some content"
        mock_post.processed = False

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cursor_result = MagicMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.all.return_value = [mock_post]
        mock_cursor_result.scalars.return_value = mock_scalar_result
        mock_db.execute.return_value = mock_cursor_result

        with patch("app.ai.pipeline.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            with patch("app.ai.pipeline.SocialExtractor") as mock_extractor_class:
                mock_extractor = AsyncMock()
                mock_extractor.extract_batch = AsyncMock(return_value=[])
                mock_extractor_class.return_value = mock_extractor

                result = await process_social_posts(mock_db, limit=20)

        # Post should be marked as processed
        assert mock_post.processed is True
        mock_db.commit.assert_called_once()

    async def test_handles_no_matching_platform(self) -> None:
        """Test that events with non-existent platforms are skipped."""
        from app.ai.extractor import ExtractedEvent
        from app.models.social_post import SocialPost

        mock_post = MagicMock(spec=SocialPost)
        mock_post.content = "Some content"
        mock_post.processed = False
        mock_post.platform = "instagram"
        mock_post.post_url = "http://example.com"

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cursor_result = MagicMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.all.return_value = [mock_post]
        mock_cursor_result.scalars.return_value = mock_scalar_result

        # Platform lookup returns None
        mock_platform_result = MagicMock()
        mock_platform_result.scalar_one_or_none.return_value = None
        mock_db.execute.side_effect = [
            mock_cursor_result,  # For SocialPost fetch
            mock_platform_result,  # For Platform lookup
        ]

        extracted = ExtractedEvent(
            product_name="Test Product",
            currency="USD",
            confidence=0.9,
        )

        with patch("app.ai.pipeline.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"
            with patch("app.ai.pipeline.SocialExtractor") as mock_extractor_class:
                mock_extractor = AsyncMock()
                mock_extractor.extract_batch = AsyncMock(return_value=[extracted])
                mock_extractor_class.return_value = mock_extractor
                with patch("app.ai.pipeline.get_or_create_product") as mock_product:
                    mock_product_obj = MagicMock()
                    mock_product_obj.id = uuid.uuid4()
                    mock_product.return_value = mock_product_obj

                    result = await process_social_posts(mock_db, limit=20)

        # No events created if platform not found
        assert result == 0
        # But post should still be marked as processed
        assert mock_post.processed is True
