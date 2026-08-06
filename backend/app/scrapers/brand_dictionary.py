"""딜 감지용 브랜드 사전 — 가격 수집용 레지스트리와 분리한다.

두 목록은 목적이 다르다:

- `brands/shopify.py:BRANDS` (26개) = **가격을 수집할 수 있는** 브랜드.
  products.json이 열려 있어야 들어간다.
- 이 파일 = **딜을 감지할** 브랜드. 가격 수집이 안 돼도, 우리가 파는 게 아니어도,
  "이 브랜드 세일이 났다"를 알아야 하면 넣는다.

둘을 같은 목록으로 쓰다가 실제로 놓쳤다 — 2026-08-06 Slickdeals 실측에서 48시간
이내 유일한 관련 딜이 `Torriden DIVE-IN … $14.9 (Costco)`였는데, 토리든은 K뷰티인데도
수집 레지스트리에 없어서 매칭이 0건으로 나왔다.

한국어 표기가 함께 필요한 이유: 같은 브랜드가 국내 소스에선 "토리든", 미국 소스에선
"Torriden"으로 나온다.
"""
from __future__ import annotations

import re

# 정본 이름 → 표기 변형(소문자 비교). 국내/해외 표기를 한 항목에 묶는다.
BRAND_ALIASES: dict[str, tuple[str, ...]] = {
    # ── K-beauty ────────────────────────────────────────────
    "Sulwhasoo": ("sulwhasoo", "설화수"),
    "Hera": ("헤라",),
    "innisfree": ("innisfree", "이니스프리"),
    "Laneige": ("laneige", "라네즈"),
    "Mamonde": ("mamonde", "마몽드"),
    "Etude House": ("etude house", "에뛰드하우스", "에뛰드"),
    "Missha": ("missha", "미샤"),
    "Nature Republic": ("nature republic", "네이처리퍼블릭"),
    "The Face Shop": ("the face shop", "더페이스샵"),
    "Dr.Jart+": ("dr.jart", "dr jart", "닥터자르트"),
    "COSRX": ("cosrx", "코스알엑스"),
    "Beauty of Joseon": ("beauty of joseon", "조선미녀"),
    "Torriden": ("torriden", "토리든"),
    "CLIO": ("clio", "클리오"),
    "rom&nd": ("rom&nd", "romand", "롬앤"),
    "3CE": ("3ce", "쓰리씨이"),
    "Tony Moly": ("tonymoly", "tony moly", "토니모리"),
    "Tamburins": ("tamburins", "탐버린즈"),
    "Some By Mi": ("some by mi", "썸바이미"),
    "Anua": ("anua", "아누아"),
    "Purito": ("purito", "퓨리토"),
    "IUNIK": ("iunik", "아이유닉"),
    "SKIN1004": ("skin1004", "스킨천사"),
    "Mixsoon": ("mixsoon", "믹순"),
    "Round Lab": ("round lab", "라운드랩"),
    "Medicube": ("medicube", "메디큐브"),
    "Isntree": ("isntree", "이즈앤트리"),
    "Klairs": ("klairs", "클레어스"),
    "Papa Recipe": ("papa recipe", "파파레서피"),
    "Benton": ("benton", "벤톤"),
    "Haruharu Wonder": ("haruharu", "하루하루원더"),
    "Numbuzin": ("numbuzin", "넘버즈인"),
    "TIRTIR": ("tirtir", "티르티르"),
    "Amorepacific": ("amorepacific", "아모레퍼시픽"),
    "Goodal": ("goodal", "구달"),
    "Abib": ("abib", "아비브"),
    "Axis-Y": ("axis-y", "axis y"),
    "Dear Klairs": ("dear klairs",),
    # ── 럭셔리 / 프레스티지 ──────────────────────────────────
    "La Mer": ("la mer", "라메르"),
    "La Prairie": ("la prairie", "라프레리"),
    "Clé de Peau Beauté": ("cle de peau", "clé de peau", "끌레드뽀"),
    "Valmont": ("valmont",),
    "Augustinus Bader": ("augustinus bader",),
    "Sisley Paris": ("sisley",),
    "Chantecaille": ("chantecaille",),
    "Tatcha": ("tatcha",),
    "Tata Harper": ("tata harper",),
    "SK-II": ("sk-ii", "skii", "sk2", "sk ii", "에스케이투"),
    "Shiseido": ("shiseido", "시세이도"),
    "Charlotte Tilbury": ("charlotte tilbury",),
    "NARS": ("nars",),
    "Hourglass": ("hourglass cosmetics", "hourglass"),
    "Pat McGrath Labs": ("pat mcgrath",),
    "Estée Lauder": ("estee lauder", "estée lauder", "에스티로더"),
    "Lancôme": ("lancome", "lancôme", "랑콤"),
    "Clinique": ("clinique", "크리니크"),
    "Kiehl's": ("kiehl", "키엘"),
    "Clarins": ("clarins", "클라랑스"),
    "Laura Mercier": ("laura mercier",),
    "Jo Malone": ("jo malone",),
    "Diptyque": ("diptyque",),
    "Byredo": ("byredo",),
    "Aesop": ("aesop",),
    "Guerlain": ("guerlain",),
    # ── 미국 인디 / DTC ─────────────────────────────────────
    "Glossier": ("glossier",),
    "Rare Beauty": ("rare beauty",),
    "MERIT": ("merit beauty", "merit"),
    "ILIA": ("ilia beauty", "ilia"),
    "Kosas": ("kosas",),
    "Saie": ("saie",),
    "Westman Atelier": ("westman atelier",),
    "Victoria Beckham Beauty": ("victoria beckham",),
    "Summer Fridays": ("summer fridays",),
    "Herbivore": ("herbivore",),
    "OSEA": ("osea",),
    "Nécessaire": ("necessaire", "nécessaire"),
    "Sunday Riley": ("sunday riley",),
    "111SKIN": ("111skin",),
    "Rhode": ("rhode skin", "rhode"),
    "Youth To The People": ("youth to the people",),
    "Drunk Elephant": ("drunk elephant",),
    "Paula's Choice": ("paula's choice", "paulas choice"),
    "The Ordinary": ("the ordinary",),
    "The Inkey List": ("the inkey list", "inkey list"),
    "Glow Recipe": ("glow recipe",),
    "CeraVe": ("cerave", "세라베"),
    "Cetaphil": ("cetaphil",),
    "e.l.f. Cosmetics": ("e.l.f.", "elf cosmetics"),
    "NYX": ("nyx professional", "nyx"),
}

# 흔한 영어 단어와 겹치는 브랜드 — 단독 등장만으로는 브랜드로 보지 않는다.
# ("fresh sale"의 fresh는 브랜드가 아니라 형용사일 가능성이 훨씬 높다)
AMBIGUOUS_BRANDS = {"Fresh", "Flower Beauty", "Milani", "Wet n Wild"}

# 한글은 \b가 동작하지 않으므로 스크립트에 따라 경계 처리를 나눈다.
_HANGUL = re.compile(r"[가-힣]")


def _pattern(alias: str) -> re.Pattern[str]:
    escaped = re.escape(alias)
    if _HANGUL.search(alias):
        return re.compile(escaped, re.I)
    return re.compile(rf"(?<![\w]){escaped}(?![\w])", re.I)


_COMPILED: list[tuple[str, str, re.Pattern[str]]] = [
    (brand, alias, _pattern(alias))
    for brand, aliases in BRAND_ALIASES.items()
    for alias in aliases
    if brand not in AMBIGUOUS_BRANDS
]


def detect_brands(text: str) -> list[str]:
    """텍스트에 등장하는 브랜드를 모두. 긴 별칭이 짧은 것을 이긴다."""
    found: dict[str, int] = {}
    for brand, alias, pattern in _COMPILED:
        if pattern.search(text):
            found[brand] = max(found.get(brand, 0), len(alias))
    return [b for b, _ in sorted(found.items(), key=lambda kv: -kv[1])]


def detect_brand(text: str) -> str | None:
    """가장 구체적인 브랜드 하나."""
    brands = detect_brands(text)
    return brands[0] if brands else None


def canonicalize_brand_mentions(text: str) -> str:
    """텍스트에 등장하는 브랜드 별칭을 정본 영문 브랜드명으로 치환한다.

    번역 전에 호출한다 — 일반 번역모델이 브랜드명을 음역해버리는 문제를 막기 위함
    (실측: "토리든"이 호출마다 "Tori Den"/"Toryden"으로 비결정적으로 오역됨).
    """
    result = text
    # 긴 별칭을 먼저 처리하기 위해 별칭 길이 내림차순으로 정렬
    for brand, alias, pattern in sorted(_COMPILED, key=lambda x: -len(x[1])):
        result = pattern.sub(brand, result)
    return result
