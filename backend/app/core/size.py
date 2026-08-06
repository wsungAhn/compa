"""용량 정규화 — 모든 용량을 ml로 환산한다.

크로스 통화 매칭의 급소다. 미국 공홈은 `2.5 oz`, 일본 리스팅은 `75ml`로 표기하는데,
정규화 없이 "용량 일치"를 요구하면 **정답 쌍까지 전부 탈락한다**(2026-08-05 실측 0/10).

소수점을 흘리면 안 된다 — 실측 버그: `(\\d{1,4})\\s?(oz)` 패턴이 `2.5 oz`를 `5oz`로
읽어 73.9ml가 147.9ml가 됐다.
"""
from __future__ import annotations

import re

FL_OZ_TO_ML = 29.5735

# 표기 변형: "2.5 oz" "2.5oz" "2.5 fl oz" "2.5 Fl. Oz." "75ml" "75 mL" "1.69 ミリ" "50g"
_SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(fl\.?\s*oz|oz|ml|mL|ミリリットル|ミリ|g\b|G\b|그램|밀리)",
    re.I,
)
# 개수 표기는 용량이 아니다("2 x 30ml"의 2, "Pack of 3"의 3)
_MULTIPACK_RE = re.compile(r"(\d+)\s*(?:x|×|팩|pack)\s*", re.I)


def parse_size_ml(text: str | None) -> float | None:
    """텍스트에서 첫 용량을 찾아 ml로 환산. 없으면 None.

    화장품은 g과 ml을 혼용하며 밀도가 1에 가까워 g≈ml로 취급한다. 정확한 환산이
    아니라 **같은 상품인지 판별하는 용도**라 이 근사로 충분하다.
    """
    if not text:
        return None
    match = _SIZE_RE.search(text)
    if not match:
        return None
    raw, unit = match.group(1).replace(",", "."), match.group(2).lower()
    try:
        value = float(raw)
    except ValueError:
        return None
    if value <= 0 or value > 10000:
        return None

    if unit.startswith("fl") or unit == "oz":
        return round(value * FL_OZ_TO_ML, 1)
    return round(value, 1)


def all_sizes_ml(text: str | None) -> list[float]:
    """텍스트에 등장하는 모든 용량(ml). 중복은 제거하고 순서는 유지한다."""
    if not text:
        return []
    out: list[float] = []
    for raw, unit in _SIZE_RE.findall(text):
        try:
            value = float(raw.replace(",", "."))
        except ValueError:
            continue
        if value <= 0 or value > 10000:
            continue
        ml = round(value * FL_OZ_TO_ML, 1) if unit.lower().startswith(("fl", "oz")) else round(value, 1)
        if ml not in out:
            out.append(ml)
    return out


def unambiguous_size_ml(text: str | None) -> float | None:
    """용량이 하나로 특정될 때만 반환한다.

    가격이 하나인데 제목에 용량이 여러 개면 그 가격을 어느 용량에 붙일지 알 수 없다.
    추측하면 거짓 비교가 나간다 — 실측: "…30m, 75ml, まとめ買い お試し" 리스팅에서
    75ml을 집어 ¥1,980(정본 $99)이 됐다. 모를 때는 모른다고 두는 게 맞다.
    """
    sizes = all_sizes_ml(text)
    return sizes[0] if len(sizes) == 1 else None


def sizes_match(a: float | None, b: float | None, tolerance: float = 0.08) -> bool:
    """두 용량이 같은 상품으로 볼 만큼 가까운가.

    tolerance는 **잠정값**이다 — SK-II 한 제품 10건에서 나왔고, 브랜드당 50건 이상을
    모은 뒤 재산정할 것(적대감사 R1·R2 지적). 한쪽이라도 모르면 판단하지 않는다:
    False를 돌려주면 "다르다"가 되어 정답까지 버리므로, 호출부가 unknown을 구분할 수
    있도록 None 입력은 True(=거부하지 않음)로 통과시킨다.
    """
    if a is None or b is None:
        return True
    if a <= 0 or b <= 0:
        return True
    larger = max(a, b)
    return abs(a - b) / larger <= tolerance


def is_multipack(text: str | None) -> bool:
    """묶음 상품은 단위 가격이 달라 같은 상품으로 비교하면 안 된다."""
    return bool(text and _MULTIPACK_RE.search(text))
