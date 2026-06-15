"""Currency conversion utilities with static fallback rates."""

# Fallback static exchange rates to KRW (TODO: integrate live rates API)
FX_RATES_TO_KRW: dict[str, float] = {
    "KRW": 1.0,
    "USD": 1380.0,
    "JPY": 9.2,
    "CNY": 190.0,
}


def convert(
    amount: float, from_currency: str, to_currency: str
) -> float | None:
    """
    Convert amount from one currency to another via KRW pivot.

    Args:
        amount: The amount to convert
        from_currency: Source currency code (e.g., 'USD', 'JPY')
        to_currency: Target currency code (e.g., 'KRW', 'CNY')

    Returns:
        Converted amount rounded to 2 decimals, or None if currency unknown.
    """
    if from_currency == to_currency:
        return round(amount, 2)

    from_rate = FX_RATES_TO_KRW.get(from_currency)
    to_rate = FX_RATES_TO_KRW.get(to_currency)

    if from_rate is None or to_rate is None:
        return None

    # Convert: amount -> KRW -> target currency
    amount_krw = amount * from_rate
    converted = amount_krw / to_rate
    return round(converted, 2)
