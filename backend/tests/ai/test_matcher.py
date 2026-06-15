"""Unit tests for product matching — normalize_name, COUNTRY_NAME_COLUMN, pure functions."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.matcher import (
    COUNTRY_NAME_COLUMN,
    find_matching_product,
    get_or_create_product,
    normalize_name,
    _ask_claude_for_match,
)
from app.models.product import Product


# ============================================================================
# Pure function tests: normalize_name
# ============================================================================


class TestNormalizeName:
    """Test normalize_name pure function."""

    def test_lowercase_conversion(self) -> None:
        """Test conversion to lowercase."""
        assert normalize_name("SULWHASOO Essence") == "sulwhasoo essence"

    def test_html_tag_removal(self) -> None:
        """Test removal of HTML tags."""
        assert normalize_name("Sulwhasoo <b>Essence</b>") == "sulwhasoo essence"
        assert normalize_name("SK-II <i>Facial</i> <b>Treatment</b>") == "sk-ii facial treatment"

    def test_whitespace_collapse(self) -> None:
        """Test collapsing repeated whitespace to single space."""
        assert normalize_name("Sulwhasoo   Essence") == "sulwhasoo essence"
        assert normalize_name("SK-II\t\tFacial") == "sk-ii facial"

    def test_strip_leading_trailing_whitespace(self) -> None:
        """Test stripping leading/trailing whitespace."""
        assert normalize_name("  Sulwhasoo Essence  ") == "sulwhasoo essence"

    def test_combined_transformations(self) -> None:
        """Test all transformations combined."""
        input_str = "  <b>SULWHASOO</b>   윤조에센스  "
        expected = "sulwhasoo 윤조에센스"
        assert normalize_name(input_str) == expected

    def test_empty_string(self) -> None:
        """Test empty string."""
        assert normalize_name("") == ""

    def test_only_whitespace(self) -> None:
        """Test string with only whitespace."""
        assert normalize_name("   ") == ""

    def test_korean_characters(self) -> None:
        """Test Korean characters are preserved and lowercased."""
        assert normalize_name("설화수 윤조에센스") == "설화수 윤조에센스"
        assert normalize_name("AMOREPACIFIC 설화수") == "amorepacific 설화수"

    def test_special_characters_preserved(self) -> None:
        """Test special characters are preserved."""
        assert normalize_name("SK-II Test") == "sk-ii test"
        assert normalize_name("Dr. G R.E.D Essence") == "dr. g r.e.d essence"


# ============================================================================
# COUNTRY_NAME_COLUMN mapping test
# ============================================================================


class TestCountryNameColumnMapping:
    """Test COUNTRY_NAME_COLUMN constant."""

    def test_mapping_completeness(self) -> None:
        """Test that all 4 countries are mapped."""
        assert "KR" in COUNTRY_NAME_COLUMN
        assert "US" in COUNTRY_NAME_COLUMN
        assert "JP" in COUNTRY_NAME_COLUMN
        assert "CN" in COUNTRY_NAME_COLUMN

    def test_mapping_values(self) -> None:
        """Test that mappings are correct."""
        assert COUNTRY_NAME_COLUMN["KR"] == "name_kr"
        assert COUNTRY_NAME_COLUMN["US"] == "name_en"
        assert COUNTRY_NAME_COLUMN["JP"] == "name_jp"
        assert COUNTRY_NAME_COLUMN["CN"] == "name_cn"


# ============================================================================
# Helper function: create Product instances for testing
# ============================================================================


def create_test_product(
    name_kr: str | None = None,
    name_en: str | None = None,
    name_jp: str | None = None,
    name_cn: str | None = None,
    brand: str | None = None,
    product_id: uuid.UUID | None = None,
) -> Product:
    """Create an in-memory Product instance for testing."""
    if product_id is None:
        product_id = uuid.uuid4()

    product = Product()
    product.id = product_id
    product.name_kr = name_kr
    product.name_en = name_en
    product.name_jp = name_jp
    product.name_cn = name_cn
    product.brand = brand
    product.created_at = datetime.now()
    product.deleted_at = None

    return product


# ============================================================================
# Pure logic test: pick_unique_brand_candidate (factored helper)
# ============================================================================


def pick_unique_brand_candidate(
    candidates: list[Product],
    brand: str | None,
) -> Product | None:
    """Helper to pick a unique candidate by brand (testable pure function)."""
    if not brand or not candidates:
        return None

    brand_lower = brand.lower()
    matching = [
        c for c in candidates
        if c.brand and c.brand.lower() == brand_lower
    ]

    if len(matching) == 1:
        return matching[0]

    return None


class TestPickUniqueBrandCandidate:
    """Test the pure helper for brand-based matching."""

    def test_single_brand_match(self) -> None:
        """Test returning when exactly one product matches brand."""
        product = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        candidates = [product]
        result = pick_unique_brand_candidate(candidates, "amorepacific")
        assert result == product

    def test_case_insensitive_brand_match(self) -> None:
        """Test brand matching is case-insensitive."""
        product = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        candidates = [product]
        result = pick_unique_brand_candidate(candidates, "amorepacific")
        assert result == product

    def test_multiple_brand_matches_returns_none(self) -> None:
        """Test returning None when multiple products match brand."""
        p1 = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        p2 = create_test_product(name_kr="기타제품", brand="AMOREPACIFIC")
        candidates = [p1, p2]
        result = pick_unique_brand_candidate(candidates, "amorepacific")
        assert result is None

    def test_no_brand_returns_none(self) -> None:
        """Test returning None when no brand is provided."""
        product = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        candidates = [product]
        result = pick_unique_brand_candidate(candidates, None)
        assert result is None

    def test_no_candidates_returns_none(self) -> None:
        """Test returning None when candidates list is empty."""
        result = pick_unique_brand_candidate([], "amorepacific")
        assert result is None

    def test_no_matching_brand_returns_none(self) -> None:
        """Test returning None when brand doesn't match."""
        product = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        candidates = [product]
        result = pick_unique_brand_candidate(candidates, "sulwhasoo")
        assert result is None


# ============================================================================
# Database-dependent tests (with mocked AsyncSession)
# ============================================================================


@pytest.mark.asyncio
class TestFindMatchingProduct:
    """Test find_matching_product with mocked database."""

    def _create_mock_db(self, products: list[Product]) -> AsyncMock:
        """Helper to create a properly mocked AsyncSession."""
        from unittest.mock import MagicMock

        mock_db = AsyncMock(spec=AsyncSession)
        mock_cursor_result = MagicMock()
        mock_scalar_result = MagicMock()
        mock_scalar_result.all.return_value = products
        mock_cursor_result.scalars.return_value = mock_scalar_result
        mock_db.execute.return_value = mock_cursor_result
        return mock_db

    async def test_exact_match_kr(self) -> None:
        """Test exact match on Korean name column."""
        product = create_test_product(name_kr="설화수 윤조에센스", brand="AMOREPACIFIC")
        mock_db = self._create_mock_db([product])

        result = await find_matching_product(
            mock_db,
            "설화수 윤조에센스",
            "AMOREPACIFIC",
            "KR",
        )

        assert result == product

    async def test_exact_match_case_insensitive(self) -> None:
        """Test exact match is case-insensitive."""
        product = create_test_product(name_en="Sulwhasoo First Care", brand="Sulwhasoo")
        mock_db = self._create_mock_db([product])

        result = await find_matching_product(
            mock_db,
            "SULWHASOO FIRST CARE",
            "Sulwhasoo",
            "US",
        )

        assert result == product

    async def test_no_match_returns_none(self) -> None:
        """Test returning None when no product matches."""
        product = create_test_product(name_en="Other Product", brand="OtherBrand")
        mock_db = self._create_mock_db([product])

        result = await find_matching_product(
            mock_db,
            "Sulwhasoo First Care",
            "Sulwhasoo",
            "US",
        )

        assert result is None

    async def test_skips_deleted_products(self) -> None:
        """Test that deleted products are not matched."""
        product = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        product.deleted_at = datetime.now()

        # When filtering for non-deleted products, database returns empty list
        mock_db = self._create_mock_db([])

        result = await find_matching_product(
            mock_db,
            "설화수",
            "AMOREPACIFIC",
            "KR",
        )

        assert result is None

    async def test_invalid_country_returns_none(self) -> None:
        """Test that invalid country code returns None."""
        mock_db = self._create_mock_db([])

        result = await find_matching_product(
            mock_db,
            "Sulwhasoo",
            "Sulwhasoo",
            "XX",  # Invalid country
        )

        assert result is None

    async def test_brand_match_with_single_candidate(self) -> None:
        """Test brand-based matching with exactly one candidate."""
        p1 = create_test_product(name_kr="설화수", brand="AMOREPACIFIC")
        p2 = create_test_product(name_kr="다른상품", brand="OtherBrand")

        mock_db = self._create_mock_db([p1, p2])

        result = await find_matching_product(
            mock_db,
            "completely different name",
            "AMOREPACIFIC",
            "KR",
        )

        assert result == p1


@pytest.mark.asyncio
class TestGetOrCreateProduct:
    """Test get_or_create_product with mocked database."""

    async def test_returns_existing_product_when_found(self) -> None:
        """Test returning existing product when match found."""
        product = create_test_product(name_en="Sulwhasoo First Care", brand="Sulwhasoo")
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock find_matching_product to return our product
        with patch("app.ai.matcher.find_matching_product", return_value=product):
            result = await get_or_create_product(
                mock_db,
                "Sulwhasoo First Care",
                "Sulwhasoo",
                "US",
            )

        assert result == product

    async def test_creates_new_product_when_not_found(self) -> None:
        """Test creating new product when no match found."""
        mock_db = AsyncMock(spec=AsyncSession)

        # Mock find_matching_product to return None
        with patch("app.ai.matcher.find_matching_product", return_value=None):
            result = await get_or_create_product(
                mock_db,
                "Sulwhasoo First Care",
                "Sulwhasoo",
                "US",
            )

        # Check that product was added to db
        mock_db.add.assert_called_once()
        assert mock_db.flush.call_count >= 1

    async def test_updates_empty_country_column(self) -> None:
        """Test updating empty country-specific name column."""
        product = create_test_product(name_kr="설화수", name_en=None, brand="Sulwhasoo")
        mock_db = AsyncMock(spec=AsyncSession)

        with patch("app.ai.matcher.find_matching_product", return_value=product):
            result = await get_or_create_product(
                mock_db,
                "Sulwhasoo First Care",
                "Sulwhasoo",
                "US",
            )

        assert result.name_en == "Sulwhasoo First Care"

    async def test_does_not_overwrite_existing_country_column(self) -> None:
        """Test that existing country column is not overwritten."""
        product = create_test_product(
            name_en="Original Name",
            brand="Sulwhasoo",
        )
        mock_db = AsyncMock(spec=AsyncSession)

        with patch("app.ai.matcher.find_matching_product", return_value=product):
            result = await get_or_create_product(
                mock_db,
                "Different Name",
                "Sulwhasoo",
                "US",
            )

        # Should remain unchanged
        assert result.name_en == "Original Name"


@pytest.mark.asyncio
class TestAskClaudeForMatch:
    """Test _ask_claude_for_match with mocked Claude API."""

    async def test_claude_returns_matching_id(self) -> None:
        """Test Claude returns a matching product ID."""
        import anthropic

        p1_id = uuid.uuid4()
        p2_id = uuid.uuid4()
        p1 = create_test_product(product_id=p1_id, name_kr="설화수", brand="AMOREPACIFIC")
        p2 = create_test_product(product_id=p2_id, name_kr="기타상품", brand="AMOREPACIFIC")

        # Mock Anthropic API response with proper TextBlock
        mock_text_block = AsyncMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = f'{{"match_id": "{p1_id}"}}'
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("app.ai.matcher.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _ask_claude_for_match(
                "설화수 윤조에센스",
                "AMOREPACIFIC",
                "KR",
                [p1, p2],
            )

        assert result == p1

    async def test_claude_returns_null_on_no_match(self) -> None:
        """Test Claude returns null when no match."""
        import anthropic

        candidates = [
            create_test_product(name_kr="설화수", brand="AMOREPACIFIC"),
            create_test_product(name_kr="기타상품", brand="AMOREPACIFIC"),
        ]

        mock_text_block = AsyncMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = '{"match_id": null}'
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("app.ai.matcher.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _ask_claude_for_match(
                "unknown product",
                "unknown brand",
                "KR",
                candidates,
            )

        assert result is None

    async def test_handles_json_parse_error(self) -> None:
        """Test that JSON parse errors are handled gracefully."""
        import anthropic

        candidates = [
            create_test_product(name_kr="설화수", brand="AMOREPACIFIC"),
        ]

        mock_text_block = AsyncMock(spec=anthropic.types.TextBlock)
        mock_text_block.text = "invalid json {{"
        mock_response = MagicMock()
        mock_response.content = [mock_text_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch("app.ai.matcher.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _ask_claude_for_match(
                "설화수",
                "AMOREPACIFIC",
                "KR",
                candidates,
            )

        assert result is None

    async def test_handles_api_error(self) -> None:
        """Test that API errors are handled gracefully."""
        candidates = [
            create_test_product(name_kr="설화수", brand="AMOREPACIFIC"),
        ]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=Exception("API Error"))

        with patch("app.ai.matcher.anthropic.AsyncAnthropic", return_value=mock_client):
            result = await _ask_claude_for_match(
                "설화수",
                "AMOREPACIFIC",
                "KR",
                candidates,
            )

        assert result is None
