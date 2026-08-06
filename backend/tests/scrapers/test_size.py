"""용량 정규화 — 크로스 통화 매칭의 급소. 실측에서 나온 실제 표기를 고정한다."""
from app.core.size import FL_OZ_TO_ML, is_multipack, parse_size_ml, sizes_match


def test_oz_is_converted_to_ml() -> None:
    """미국 공홈은 oz, 일본 리스팅은 ml — 정규화 없이는 정답 쌍까지 탈락한다(실측 0/10)."""
    assert parse_size_ml("2.5 oz") == 73.9
    assert parse_size_ml("1.69 oz") == 50.0
    assert parse_size_ml("11 oz") == 325.3


def test_decimals_are_not_dropped() -> None:
    """실측 버그: (\\d{1,4})(oz) 패턴이 "2.5 oz"를 "5oz"로 읽어 73.9가 147.9가 됐다."""
    assert parse_size_ml("2.5 oz") != parse_size_ml("5 oz")
    assert parse_size_ml("5 oz") == round(5 * FL_OZ_TO_ML, 1)


def test_fl_oz_variants() -> None:
    assert parse_size_ml("1.7 Fl. Oz.") == 50.3
    assert parse_size_ml("2.5 Fl Oz") == 73.9


def test_ml_and_gram_forms() -> None:
    """화장품은 g과 ml을 혼용하고 밀도가 1에 가까워 g≈ml로 본다."""
    assert parse_size_ml("75ml") == 75.0
    assert parse_size_ml("75 mL") == 75.0
    assert parse_size_ml("230mL") == 230.0
    assert parse_size_ml("50g") == 50.0


def test_extracts_from_a_real_japanese_listing() -> None:
    title = "【国内正規品】SK-II フェイシャルトリートメント エッセンス 75mL"
    assert parse_size_ml(title) == 75.0


def test_absent_or_absurd_sizes_are_none() -> None:
    assert parse_size_ml("no size here") is None
    assert parse_size_ml("") is None
    assert parse_size_ml(None) is None
    assert parse_size_ml("99999 ml") is None


def test_the_pair_that_motivated_this() -> None:
    """JP 75ml ↔ US 2.5oz(73.9ml). 이 한 쌍을 붙이려고 만든 모듈이다."""
    assert sizes_match(parse_size_ml("75ml"), parse_size_ml("2.5 oz"))


def test_different_sizes_are_rejected() -> None:
    """30ml 미니어처와 73.9ml 본품을 묶으면 "일본이 3배 싸다"는 거짓이 나간다."""
    assert not sizes_match(30.0, 73.9)


def test_50ml_matches_1_7oz() -> None:
    """적대감사 R2가 "거부된다"고 주장한 쌍 — 실제로는 매칭된다(감사 산수 오류)."""
    assert sizes_match(parse_size_ml("50ml"), parse_size_ml("1.7 fl oz"))


def test_unknown_size_does_not_reject() -> None:
    """한쪽을 모르면 "다르다"가 아니다 — 모른다고 정답을 버리면 안 된다."""
    assert sizes_match(75.0, None)
    assert sizes_match(None, None)


def test_multipack_is_flagged() -> None:
    assert is_multipack("SK-II Essence 2 x 30ml")
    assert not is_multipack("SK-II Essence 75ml")
