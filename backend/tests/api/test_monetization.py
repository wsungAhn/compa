"""Tests for affiliate link conversion and premium tier gating."""
from unittest.mock import MagicMock

from app.core.affiliate import to_affiliate_url
from app.core.premium import is_premium_key, parse_premium_keys


class TestParseAndValidatePremiumKeys:
    """Tests for premium API key parsing and validation."""

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string returns empty set."""
        result = parse_premium_keys("")
        assert result == set()

    def test_parse_single_key(self) -> None:
        """Test parsing single key."""
        result = parse_premium_keys("key123")
        assert result == {"key123"}

    def test_parse_multiple_keys(self) -> None:
        """Test parsing comma-separated keys."""
        result = parse_premium_keys("key1,key2,key3")
        assert result == {"key1", "key2", "key3"}

    def test_parse_with_whitespace(self) -> None:
        """Test parsing with whitespace around keys."""
        result = parse_premium_keys("key1 , key2 , key3")
        assert result == {"key1", "key2", "key3"}

    def test_parse_with_trailing_comma(self) -> None:
        """Test parsing with trailing comma and empty entries."""
        result = parse_premium_keys("key1,key2,")
        assert result == {"key1", "key2"}

    def test_parse_with_only_whitespace(self) -> None:
        """Test parsing string with only whitespace and commas."""
        result = parse_premium_keys(" , , ")
        assert result == set()

    def test_is_premium_key_valid(self, monkeypatch: MagicMock) -> None:
        """Test is_premium_key with valid key."""
        from app.core import premium

        monkeypatch.setattr(premium, "settings", MagicMock(premium_api_keys="key1,key2,key3"))
        assert is_premium_key("key1") is True
        assert is_premium_key("key2") is True

    def test_is_premium_key_invalid(self, monkeypatch: MagicMock) -> None:
        """Test is_premium_key with invalid key."""
        from app.core import premium

        monkeypatch.setattr(premium, "settings", MagicMock(premium_api_keys="key1,key2"))
        assert is_premium_key("key3") is False

    def test_is_premium_key_none(self, monkeypatch: MagicMock) -> None:
        """Test is_premium_key with None."""
        from app.core import premium

        monkeypatch.setattr(premium, "settings", MagicMock(premium_api_keys="key1,key2"))
        assert is_premium_key(None) is False

    def test_is_premium_key_empty_string(self, monkeypatch: MagicMock) -> None:
        """Test is_premium_key with empty string."""
        from app.core import premium

        monkeypatch.setattr(premium, "settings", MagicMock(premium_api_keys="key1,key2"))
        assert is_premium_key("") is False

    def test_is_premium_key_empty_config(self, monkeypatch: MagicMock) -> None:
        """Test is_premium_key when premium_api_keys config is empty."""
        from app.core import premium

        monkeypatch.setattr(premium, "settings", MagicMock(premium_api_keys=""))
        assert is_premium_key("key1") is False


class TestAffiliateUrlConversion:
    """Tests for affiliate link conversion."""

    def test_to_affiliate_url_none_input(self) -> None:
        """Test None URL returns None."""
        result = to_affiliate_url(None, "Amazon US")
        assert result is None

    def test_amazon_partner_tag_append(self, monkeypatch: MagicMock) -> None:
        """Test Amazon tag is appended to URL."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="compa-20",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://amazon.com/dp/B001234567"
        result = to_affiliate_url(url, "Amazon US")
        assert result is not None
        assert "tag=compa-20" in result
        assert "amazon.com" in result

    def test_amazon_with_existing_query_params(self, monkeypatch: MagicMock) -> None:
        """Test Amazon URL with existing query parameters."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="compa-20",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://amazon.com/dp/B001234567?ref=something"
        result = to_affiliate_url(url, "Amazon US")
        assert result is not None
        assert "tag=compa-20" in result
        assert "ref=something" in result

    def test_amazon_already_tagged_unchanged(self, monkeypatch: MagicMock) -> None:
        """Test Amazon URL that already has a tag parameter remains unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="compa-20",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://amazon.com/dp/B001234567?tag=other-123"
        result = to_affiliate_url(url, "Amazon US")
        assert result == url

    def test_amazon_not_amazon_domain(self, monkeypatch: MagicMock) -> None:
        """Test Amazon platform but non-Amazon URL returns unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="compa-20",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://example.com/product"
        result = to_affiliate_url(url, "Amazon US")
        assert result == url

    def test_amazon_no_config_unchanged(self, monkeypatch: MagicMock) -> None:
        """Test Amazon URL with no configured partner tag returns unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://amazon.com/dp/B001234567"
        result = to_affiliate_url(url, "Amazon US")
        assert result == url

    def test_rakuten_wrap_format(self, monkeypatch: MagicMock) -> None:
        """Test Rakuten URL is wrapped with affiliate wrapper."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="12345678-1234",
            coupang_partner_id="",
        ))
        url = "https://rakuten.co.jp/item/123"
        result = to_affiliate_url(url, "Rakuten")
        assert result is not None
        assert "hb.afl.rakuten.co.jp/hgc/12345678-1234" in result
        assert "pc=" in result
        # URL should be URL-encoded in the pc parameter
        assert "rakuten.co.jp%2Fitem%2F123" in result

    def test_rakuten_not_rakuten_domain(self, monkeypatch: MagicMock) -> None:
        """Test Rakuten platform but non-Rakuten URL returns unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="12345678-1234",
            coupang_partner_id="",
        ))
        url = "https://example.com/product"
        result = to_affiliate_url(url, "Rakuten")
        assert result == url

    def test_rakuten_no_config_unchanged(self, monkeypatch: MagicMock) -> None:
        """Test Rakuten URL with no configured affiliate ID returns unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://rakuten.co.jp/item/123"
        result = to_affiliate_url(url, "Rakuten")
        assert result == url

    def test_coupang_lptag_append(self, monkeypatch: MagicMock) -> None:
        """Test Coupang lptag is appended to URL."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="compa001",
        ))
        url = "https://coupang.com/vp/products/123"
        result = to_affiliate_url(url, "쿠팡")
        assert result is not None
        assert "lptag=compa001" in result
        assert "coupang.com" in result

    def test_coupang_with_existing_query_params(self, monkeypatch: MagicMock) -> None:
        """Test Coupang URL with existing query parameters."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="compa001",
        ))
        url = "https://coupang.com/vp/products/123?ref=search"
        result = to_affiliate_url(url, "쿠팡")
        assert result is not None
        assert "lptag=compa001" in result
        assert "ref=search" in result

    def test_coupang_already_tagged_unchanged(self, monkeypatch: MagicMock) -> None:
        """Test Coupang URL that already has lptag parameter remains unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="compa001",
        ))
        url = "https://coupang.com/vp/products/123?lptag=other"
        result = to_affiliate_url(url, "쿠팡")
        assert result == url

    def test_coupang_not_coupang_domain(self, monkeypatch: MagicMock) -> None:
        """Test Coupang platform but non-Coupang URL returns unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="compa001",
        ))
        url = "https://example.com/product"
        result = to_affiliate_url(url, "쿠팡")
        assert result == url

    def test_coupang_no_config_unchanged(self, monkeypatch: MagicMock) -> None:
        """Test Coupang URL with no configured partner ID returns unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="",
            rakuten_affiliate_id="",
            coupang_partner_id="",
        ))
        url = "https://coupang.com/vp/products/123"
        result = to_affiliate_url(url, "쿠팡")
        assert result == url

    def test_unknown_platform_unchanged(self, monkeypatch: MagicMock) -> None:
        """Test unknown platform returns URL unchanged."""
        from app.core import affiliate

        monkeypatch.setattr(affiliate, "settings", MagicMock(
            amazon_partner_tag="compa-20",
            rakuten_affiliate_id="12345678-1234",
            coupang_partner_id="compa001",
        ))
        url = "https://example.com/product"
        result = to_affiliate_url(url, "UnknownPlatform")
        assert result == url

    def test_empty_string_url(self) -> None:
        """Test empty string URL returns None."""
        result = to_affiliate_url("", "Amazon US")
        assert result is None
