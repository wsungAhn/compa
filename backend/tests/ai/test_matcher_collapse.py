"""브랜드 지름길이 카탈로그를 무너뜨리던 문제 — 2026-08-06 실측 회귀 방지."""
from app.ai.matcher import _same_product_evidence


class _P:
    def __init__(self, en: str | None = None, kr: str | None = None) -> None:
        self.name_en, self.name_kr, self.name_jp, self.name_cn = en, kr, None, None


_EXISTING = _P(en="SK-II Facial Treatment Essence - Anti-Aging Essence Skincare")


def test_same_product_different_wording_is_merged() -> None:
    assert _same_product_evidence(_EXISTING, "pitera™ facial treatment essence")


def test_different_product_type_is_never_merged() -> None:
    """"Facial Treatment Essence"와 "Facial Treatment Mask"는 3토큰을 공유한다 —
    종류가 다르면 이름이 겹쳐도 같은 제품이 아니다."""
    assert not _same_product_evidence(_EXISTING, "pitera™ facial treatment mask")
    assert not _same_product_evidence(_EXISTING, "pitera™ facial treatment cleanser")


def test_single_shared_token_is_not_enough() -> None:
    """"essence" 하나만 겹치는 다른 라인을 같은 제품으로 보면 카탈로그가 무너진다.
    실측: SK-II 8개 제품이 한 행으로 합쳐졌다."""
    assert not _same_product_evidence(_EXISTING, "skinpower re-new essence")
    assert not _same_product_evidence(_EXISTING, "lxp ultimate revival essence")


def test_empty_or_unknown_names_do_not_merge() -> None:
    assert not _same_product_evidence(_EXISTING, "")
    assert not _same_product_evidence(_P(), "facial treatment essence")


def test_korean_name_column_is_considered() -> None:
    candidate = _P(kr="설화수 윤조에센스")
    assert _same_product_evidence(candidate, "설화수 윤조에센스 60ml")


def test_single_token_canonical_name_is_matched() -> None:
    """정본 이름이 토큰 하나뿐이면 그 토큰이 곧 정체성이다."""
    assert _same_product_evidence(_P(kr="윤조에센스"), "설화수 윤조에센스 60ml")


def test_short_generic_single_token_does_not_match() -> None:
    """"oil" 같은 짧은 일반어가 단일 토큰 예외를 타면 안 된다."""
    assert not _same_product_evidence(_P(en="oil"), "cleansing oil 200ml")
