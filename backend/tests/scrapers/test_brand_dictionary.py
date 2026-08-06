"""딜 감지용 브랜드 사전 — 수집 레지스트리와 분리한 이유를 테스트로 고정한다."""
from app.scrapers.brand_dictionary import (
    AMBIGUOUS_BRANDS,
    BRAND_ALIASES,
    detect_brand,
    detect_brands,
)
from app.scrapers.brands.shopify import BRANDS


def test_detects_the_brand_the_collection_registry_missed() -> None:
    """2026-08-06 Slickdeals 실측에서 48시간 내 유일한 관련 딜이었는데
    수집 레지스트리에 없어 매칭 0건이 됐던 케이스."""
    title = "Torriden DIVE-IN Low-Molecular Hyaluronic Acid Serum Set 1.69 oz $14.9"
    assert detect_brand(title) == "Torriden"
    assert "Torriden" not in {b for _n, _d, b in BRANDS}  # 수집 대상은 아니다


def test_korean_and_english_forms_map_to_one_brand() -> None:
    """같은 브랜드가 국내 소스에선 한글, 미국 소스에선 영문으로 나온다."""
    assert detect_brand("토리든 다이브인 세럼 할인") == "Torriden"
    assert detect_brand("설화수 윤조에센스 세일") == "Sulwhasoo"
    assert detect_brand("Sulwhasoo First Care Serum 20% off") == "Sulwhasoo"


def test_common_word_brands_do_not_false_positive() -> None:
    """"Fresh"는 브랜드이기도 하지만 형용사일 확률이 훨씬 높다."""
    assert detect_brand("fresh sale on produce today") is None
    assert AMBIGUOUS_BRANDS  # 가드가 비어버리면 이 테스트가 무의미해진다


def test_word_boundary_prevents_substring_matches() -> None:
    assert detect_brand("narsissism is not a brand") is None
    assert detect_brand("NARS blush 30% off") == "NARS"


def test_multiple_brands_are_all_returned() -> None:
    found = detect_brands("Sephora sale: Tatcha, Glossier, and SK-II all discounted")
    assert {"Tatcha", "Glossier", "SK-II"} <= set(found)


def test_longest_alias_wins_for_single_pick() -> None:
    assert detect_brand("beauty of joseon rice sunscreen deal") == "Beauty of Joseon"


def test_detection_dictionary_is_wider_than_collection_registry() -> None:
    """분리한 이유 자체 — 감지 범위가 수집 범위보다 넓어야 한다."""
    assert len(BRAND_ALIASES) > len(BRANDS) * 2
