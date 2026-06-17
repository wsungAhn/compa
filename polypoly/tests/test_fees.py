import pytest
from src.fees import taker_fee, net_spread, fee_adjusted_edge


def test_known_categories() -> None:
    assert taker_fee("sports") == 0.03
    assert taker_fee("crypto") == 0.07
    assert taker_fee("geopolitics") == 0.00
    assert taker_fee("world") == 0.00


def test_unknown_falls_back_to_other() -> None:
    assert taker_fee("unknown_xyz") == 0.05


def test_case_insensitive() -> None:
    assert taker_fee("Sports") == taker_fee("sports")
    assert taker_fee("CRYPTO") == taker_fee("crypto")


def test_net_spread_positive() -> None:
    assert net_spread(0.05, "sports") == pytest.approx(0.02)


def test_net_spread_negative_when_fee_large() -> None:
    assert net_spread(0.02, "crypto") < 0


def test_fee_adjusted_edge_positive() -> None:
    # spread=0.07, 2*sports_fee=0.06 → edge=0.01
    assert fee_adjusted_edge(0.48, 0.55, "sports") == pytest.approx(0.01)


def test_fee_adjusted_edge_negative_tight_spread() -> None:
    # spread=0.02, 2*crypto_fee=0.14 → negative
    assert fee_adjusted_edge(0.49, 0.51, "crypto") < 0
