"""Currency conversion tests."""
from app.core.fx import convert


def test_convert_same_currency() -> None:
    """Converting to same currency returns same amount."""
    result = convert(1000.0, "KRW", "KRW")
    assert result == 1000.0


def test_convert_usd_to_krw() -> None:
    """Convert USD to KRW at static rate."""
    # 1 USD = 1380 KRW
    result = convert(100.0, "USD", "KRW")
    assert result == 138000.0


def test_convert_krw_to_usd() -> None:
    """Convert KRW to USD (reverse)."""
    # 138000 KRW should be ~100 USD at rate 1380
    result = convert(138000.0, "KRW", "USD")
    assert result is not None
    assert abs(result - 100.0) < 0.1


def test_convert_jpy_to_krw() -> None:
    """Convert JPY to KRW at static rate."""
    # 1 JPY = 9.2 KRW
    result = convert(1000.0, "JPY", "KRW")
    assert result == 9200.0


def test_convert_cny_to_krw() -> None:
    """Convert CNY to KRW at static rate."""
    # 1 CNY = 190 KRW
    result = convert(100.0, "CNY", "KRW")
    assert result == 19000.0


def test_convert_jpy_to_cny_via_pivot() -> None:
    """Convert JPY to CNY via KRW pivot."""
    # 1000 JPY = 9200 KRW, 9200 KRW / 190 = ~48.42 CNY
    result = convert(1000.0, "JPY", "CNY")
    assert result is not None
    assert abs(result - 48.42) < 0.01


def test_convert_unknown_from_currency() -> None:
    """Unknown from_currency returns None."""
    result = convert(100.0, "GBP", "KRW")
    assert result is None


def test_convert_unknown_to_currency() -> None:
    """Unknown to_currency returns None."""
    result = convert(100.0, "KRW", "GBP")
    assert result is None


def test_convert_both_unknown() -> None:
    """Unknown both currencies returns None."""
    result = convert(100.0, "GBP", "AUD")
    assert result is None


def test_convert_rounds_to_two_decimals() -> None:
    """Result is rounded to 2 decimal places."""
    # 1234.5678 KRW to USD at rate 1380 should round nicely
    result = convert(1234.5678, "KRW", "USD")
    assert result is not None
    assert result == round(result, 2)
    # Should be approximately 0.89 (1234.5678 / 1380 = 0.894...)
    assert abs(result - 0.89) < 0.01


def test_convert_zero_amount() -> None:
    """Converting zero returns zero."""
    result = convert(0.0, "USD", "KRW")
    assert result == 0.0


def test_convert_negative_amount() -> None:
    """Converting negative amounts works (no validation)."""
    result = convert(-100.0, "USD", "KRW")
    assert result == -138000.0
