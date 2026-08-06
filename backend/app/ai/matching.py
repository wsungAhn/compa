"""크로스 통화 매칭 코어 — 순수 함수. DB·번역·LLM에 닿지 않는다.

자카드 유사도는 실측에서 정답 쌍을 0.25로 떨어뜨렸다 — JP 리스팅은 별칭·노이즈로 토큰이
과잉이라 분모가 부푼다. "포함도"(정본 토큰이 리스팅에 얼마나 들어있나)로 바꾸자 같은
쌍이 1.00이 됐다(design-cross-currency-matching-2026-08-05.md 측정 4). 매칭에 성공한
쌍이 샘플/트라이얼일 수 있고(お試し 등), 반대로 진짜 깊은 할인도 같은 가격 신호를
내므로 키워드·단가 이탈을 함께 걸릴 때만 자동 거부한다(적대감사 R2).
"""
from __future__ import annotations

import re

from app.core.size import sizes_match


_MARKETING_STOPWORDS = {"pitera", "lxp"}
# 정본 이름에 붙는 상표·마케팅 토큰 — 실측(SK-II PITERA™, LXP)에서 나온 것만 우선 등재.
# 새 사례가 나오면 추가한다(포괄적 화이트리스트를 미리 만들지 않는다 — YAGNI).

_SAMPLE_KEYWORDS = ("お試し", "トライアル", "sample", "mini", "ミニ", "decant", "분장", "分装")


def strip_noise(text: str) -> str:
    """일본 리스팅 판촉 노이즈를 제거하고 공백을 정리한다.

    - 【...】로 감싼 구간은 내용과 무관하게 통째로 제거한다(임의의 판촉 문구를 다 나열할
      수 없으므로 괄호 자체를 노이즈 마커로 취급 — 실측: 国内正規品/公式/送料無料/
      ふるさと納税 등 내용이 매번 다르다).
    - 괄호 밖에 단독으로 나오는 판촉 단어(正規品, 並行輸入品, 送料無料, 公式)도 제거한다
      (실측: "【公式】【送料無料】【ふるさと納税】正規品 並行輸入品 SK-II …"처럼 마지막
      두 단어는 괄호 밖에 있다).
    - 연속 공백을 하나로 접고 앞뒤를 자른다.
    """
    text = re.sub(r"【[^】]*】", "", text)
    text = re.sub(r"(正規品|並行輸入品|送料無料|公式)", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _name_tokens(text: str) -> set[str]:
    """Simple tokenizer for matching — lowercase, alphanumeric + Hangul + Japanese chars only."""
    cleaned = re.sub(r"[^\w가-힣ぁ-んァ-ン一-龥]+", " ", text.lower())
    return {w for w in cleaned.split() if len(w) > 1}


def containment_score(canonical: str, listing: str) -> float:
    """정본 이름의 토큰이 리스팅 텍스트에 얼마나 포함되는가 (0.0~1.0).

    canonical 쪽 상표·마케팅 토큰(_MARKETING_STOPWORDS)은 분모에서 뺀다 — 정본이
    화려할수록 매칭이 어려워지는 역전을 막기 위함(실측: 뺐더니 0.25 → 1.00).
    listing은 먼저 strip_noise를 거쳐 토큰화한다. canonical 토큰이 하나도 없으면 0.0.
    """
    canonical_tokens = _name_tokens(canonical)
    if not canonical_tokens:
        return 0.0

    filtered_canonical_tokens = canonical_tokens - _MARKETING_STOPWORDS
    if not filtered_canonical_tokens:
        return 0.0

    listing_tokens = _name_tokens(strip_noise(listing))
    if not listing_tokens:
        return 0.0

    contained_count = len(filtered_canonical_tokens & listing_tokens)
    return contained_count / len(filtered_canonical_tokens)


def is_sample_listing(text: str) -> bool:
    """샘플/트라이얼 표기가 있는가. 대소문자 무시(영문만), 부분 문자열 매칭."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in _SAMPLE_KEYWORDS)


MATCH = "match"
REJECT = "reject"
NEEDS_REVIEW = "needs_review"


def evaluate_match(
    canonical_name: str,
    listing_name: str,
    *,
    canonical_size_ml: float | None = None,
    listing_size_ml: float | None = None,
    canonical_unit_price: float | None = None,
    listing_unit_price: float | None = None,
    containment_threshold: float = 0.6,
    price_deviation_ratio: float = 1 / 3,
) -> str:
    """match / reject / needs_review 중 하나. 위 표를 그대로 구현한다."""
    if containment_score(canonical_name, listing_name) < containment_threshold:
        return REJECT

    if canonical_size_ml is not None and listing_size_ml is not None:
        if not sizes_match(canonical_size_ml, listing_size_ml):
            return REJECT

    has_sample_keyword = is_sample_listing(listing_name)
    has_price_deviation = (
        canonical_unit_price is not None
        and listing_unit_price is not None
        and canonical_unit_price > 0
        and listing_unit_price < canonical_unit_price * price_deviation_ratio
    )

    if has_sample_keyword and has_price_deviation:
        return REJECT
    elif has_sample_keyword or has_price_deviation:
        return NEEDS_REVIEW
    else:
        return MATCH