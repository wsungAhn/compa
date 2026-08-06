"""Tests for cross-country matching core logic (B-stage)."""
import pytest

from app.ai.matching import (
    strip_noise,
    containment_score,
    is_sample_listing,
    evaluate_match,
    MATCH,
    REJECT,
    NEEDS_REVIEW,
)


class TestStripNoise:
    """Test Task 1: Japanese promotional noise removal."""
    
    def test_japanese_brackets_removed(self):
        """Test 【...】 sections are removed."""
        input_text = "【公式】【送料無料】【ふるさと納税】正規品 並行輸入品 SK-II フェイシャルトリートメント エッセンス 75mL"
        expected = "SK-II フェイシャルトリートメント エッセンス 75mL"
        result = strip_noise(input_text)
        assert result == expected
    
    def test_domestic_brand_removed(self):
        """Test domestic brand notation removal (from size.py test)."""
        input_text = "【国内正規品】SK-II フェイシャルトリートメント エッセンス 75mL"
        expected = "SK-II フェイシャルトリートメント エッセンス 75mL"
        result = strip_noise(input_text)
        assert result == expected
    
    def test_english_unchanged(self):
        """Test English text is unaffected (no-op)."""
        input_text = "Laneige Water Bank Cream 50ml"
        result = strip_noise(input_text)
        assert result == input_text
    
    def test_standalone_promo_words_removed(self):
        """Test standalone promotional words outside brackets are removed."""
        input_text = "SK-II フェイシャルトリートメント エッセンス 75mL 正規品 並行輸入品"
        expected = "SK-II フェイシャルトリートメント エッセンス 75mL"
        result = strip_noise(input_text)
        assert result == expected


class TestContainmentScore:
    """Test Task 2: Containment scoring for name matching."""
    
    def test_pitera_removal_boosts_score(self):
        """Test PITERA removal from canonical boosts score (real measurement: 0.25 → 1.0)."""
        canonical = "PITERA™ Facial Treatment Essence"
        listing = "SK-II Facial Treatment Essence 75mL"
        result = containment_score(canonical, listing)
        assert result >= 0.6
    
    def test_brand_official_name_matching(self):
        """Test brand-less official names also match (official site doesn't include brand)."""
        canonical = "The Water Cream"
        listing = "La Mer The Water Cream 30mL"
        result = containment_score(canonical, listing)
        assert result >= 0.6
    
    def test_unrelated_names_low_score(self):
        """Test unrelated names score below threshold."""
        canonical = "Facial Treatment Essence"
        listing = "Random Sunscreen SPF50"
        result = containment_score(canonical, listing)
        assert result < 0.6
    
    def test_empty_canonical_zero(self):
        """Test empty canonical returns 0.0."""
        canonical = ""
        listing = "anything"
        result = containment_score(canonical, listing)
        assert result == 0.0


class TestIsSampleListing:
    """Test Task 3: Sample/trial detection."""
    
    def test_japanese_sample_keywords(self):
        """Test Japanese sample keywords detected."""
        text = "【お試し】SK-II Facial Treatment Essence Trial 75mL"
        assert is_sample_listing(text) is True
    
    def test_no_sample_keywords(self):
        """Test normal listing without sample keywords."""
        text = "SK-II Facial Treatment Essence 75mL"
        assert is_sample_listing(text) is False
    
    def test_mini_set_detected(self):
        """Test 'mini' keyword detected as sample."""
        text = "Laneige mini set"
        assert is_sample_listing(text) is True


class TestEvaluateMatch:
    """Test Task 4: Integrated matching evaluation."""
    
    def test_match_case(self):
        """Test successful match case."""
        result = evaluate_match(
            "PITERA™ Facial Treatment Essence",
            "SK-II Facial Treatment Essence 75mL",
            canonical_size_ml=73.9,
            listing_size_ml=75.0,
        )
        assert result == MATCH
    
    def test_reject_size_mismatch(self):
        """Test rejection for size mismatch."""
        result = evaluate_match(
            "PITERA™ Facial Treatment Essence",
            "SK-II Facial Treatment Essence 75mL",
            canonical_size_ml=73.9,
            listing_size_ml=30.0,
        )
        assert result == REJECT
    
    def test_match_with_noise_stripped(self):
        """Test match maintained after noise removal."""
        result = evaluate_match(
            "PITERA™ Facial Treatment Essence",
            "【お得】SK-II Facial Treatment Essence 75mL",
            canonical_size_ml=73.9,
            listing_size_ml=75.0,
        )
        assert result == MATCH
    
    def test_reject_sample_plus_price_deviation(self):
        """Test rejection for sample + price deviation (both conditions)."""
        result = evaluate_match(
            "PITERA™ Facial Treatment Essence",
            "【お試し】SK-II Facial Treatment Essence Trial 75mL",
            canonical_size_ml=73.9,
            listing_size_ml=75.0,
            canonical_unit_price=1.34,
            listing_unit_price=0.20,
        )
        assert result == REJECT
    
    def test_needs_review_price_deviation_only(self):
        """Test needs_review for price deviation only (R2: don't auto-reject real discounts)."""
        result = evaluate_match(
            "PITERA™ Facial Treatment Essence",
            "SK-II Facial Treatment Essence 75mL",
            canonical_size_ml=73.9,
            listing_size_ml=75.0,
            canonical_unit_price=1.34,
            listing_unit_price=0.20,
        )
        assert result == NEEDS_REVIEW
    
    def test_match_brand_official_name(self):
        """Test brand-less official name matching."""
        result = evaluate_match(
            "The Water Cream",
            "La Mer The Water Cream 30mL",
            canonical_size_ml=30.0,
            listing_size_ml=30.0,
        )
        assert result == MATCH