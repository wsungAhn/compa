"""다국어 제품명 매칭 (Claude API / Ollama 로컬, 규칙 기반 + LLM 하이브리드)."""
import datetime
import hashlib
import json
import logging
import re

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from app.ai.local_client import local_chat
from app.core.config import settings

_logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a cosmetics product name matcher specializing in multilingual product identification. Your task is to determine with high precision whether two product names, regardless of language, packaging, or formatting, refer to the exact same physical product.

SAME PRODUCT EXAMPLES (15+ cases across languages and formats):
1. "설화수 윤조에센스" = "Sulwhasoo First Care Activating Serum" = "雪花秀第一滋养精华" (Korean/English/Chinese, same essence product)
2. "SK-II 피테라 에센스" = "SK-II Facial Treatment Essence" = "SK-IIフェイシャルトリートメントエッセンス" (same iconic essence, 3 languages)
3. "라네즈 수프림 나이트 에센스" = "Laneige Advanced Night Repair Essence Intensive" (same night essence, Korean/English)
4. "에스티로더 더블웨어" = "Estée Lauder Double Wear" = "雙倍精油粉底液" (foundation in 3 languages)
5. "MAC Face & Body" = "MAC F&B" = "MACF&B ファンデーション" (abbreviations, different sizes count as same)
6. "資生堂 アデノバイタル" = "Shiseido Adenovital" = "资生堂 艾德法官" (Japanese brand, transliterated across languages)
7. "BBクリーム" = "BB Cream" = "BB霜" (abbreviated acronym, multilingual)
8. "コンシーラー SPF15" = "Concealer SPF15" = "遮瑕膏 SPF15" (same product, different language SPF specs)
9. "ロレアル パリ シーケンシャル" = "L'Oreal Paris Sequential" (French brand, katakana/English)
10. "香奈儿 山茶花潤唇膏" = "Chanel Camellia Lip Balm" (Chinese/English for same lip product)
11. "더마 라 로셰 안테리우스 XL" = "La Roche-Posay Anthelios XL SPF 50+" (Korean/English, same sunscreen)
12. "JILL STUART ブロッサムティー コンシーラー" = "Jill Stuart Blossom Tea Concealer" (Japanese/English concealer, same product)
13. "クリニーク ターン アラウンド セラム" = "Clinique Turnaround Serum Intensive Renewal" (Japanese/English serum)
14. "루이비통 향수" = "Louis Vuitton Perfume" (Korean/English fragrance equivalent)
15. "바디가드 크림 50ml" = "Body Guard Cream 50mL" (size in different languages, same product)

DIFFERENT PRODUCT EXAMPLES (12+ near-miss cases to avoid false positives):
1. "헤라 UV 미스트 쿠션" ≠ "헤라 블랙 쿠션" (same brand HERA, but UV Mist cushion ≠ Black cushion—different finish formulations and UV protection)
2. "NARS 라디언트 파우더" ≠ "NARS 벨벳 매트 파우더" (same brand NARS, but Radiant (luminous) ≠ Velvet Matte (matte)—incompatible finishes, different product lines)
3. "Maybelline Fit Me" ≠ "Maybelline Superstay" (same brand, different foundation lines—distinct formulations, wear time, coverage)
4. "Olay Total Effects" ≠ "Olay Regenerist" (same brand, different anti-aging lines—different actives and benefits)
5. "兰蔻粉水" ≠ "兰蔻眼霜" (same brand Lancôme, but toner ≠ eye cream—different product categories and use areas)
6. "SK-II エッセンス 75ml" ≠ "SK-II クリーム" (same brand, but essence ≠ cream—fundamentally different product types with different textures)
7. "資生堂 赤いコンパクト" ≠ "資生堂 青いコンパクト" (same brand Shiseido, same powder compact style but different SKUs with distinct formulas)
8. "Dior Rouge" (lipstick) ≠ "Dior Blush" (cheek product) (same brand, completely different categories and application areas)
9. "Clinique Dramatically Different" ≠ "Clinique Moisturizing Cream" (same brand, but two different moisturizer lines with different formulas)
10. "雅漾舒缓喷雾" ≠ "雅漾防晒喷雾" (same brand Avène, but thermal water spray ≠ sunscreen spray—different purposes)
11. "Laneige Water Sleeping Mask" ≠ "Laneige Night Cream" (same brand, both nighttime but mask ≠ cream—different product type and application method)
12. "Cetaphil Cream" ≠ "Cetaphil Lotion" (same brand, but cream (thicker) ≠ lotion (lighter)—different texture and use case)

REASONING APPROACH (step-by-step evaluation):
1. Extract core product identity: Identify the primary product category (essence, foundation, lipstick, cream, etc.) by removing brand, size, texture modifiers.
2. Check brand transliteration: Verify brand names match after accounting for language transliteration (Korean→English, Chinese→English, Japanese→English).
3. Identify texture/finish as core differentiator: If one product is "Matte" and another is "Luminous" or "Dewy," they are different. Do NOT count texture as just a variant.
4. Exclude size/packaging as differentiators: "200ml" vs "300ml" or "Compact #1" vs "Compact #2" does NOT make them different products—only the formula/product name matters.
5. Transliteration equivalence: Brand transliterations (兰蔻→Lancôme→ランコム) count as same. Korean hangul, English romaji, Chinese pinyin all map to one brand if they phonetically match.
6. Confidence scoring: Use confidence 0.95+ only for clear linguistic matches across 2+ languages OR exact rule-based matches. Use 0.7–0.85 for partial matches requiring interpretation. Use <0.5 for ambiguous cases.

COMMON MISTAKES TO AVOID:
- ❌ Treating size variants as different products ("100ml essence" = "200ml essence" → true, not false; volume differences do not create different products)
- ❌ Treating shade variants as different products ("Shade 01 Lipstick" and "Shade 02 Lipstick" of same line → true, not false; color/shade is NOT a product differentiator)
- ❌ Matching on brand alone without product type ("Chanel foundation" ≠ "Chanel lipstick" despite same brand; product type is essential)
- ❌ Ignoring core finish/texture descriptors ("Matte powder" ≠ "Luminous powder" → false, different finishes ARE product differentiators)
- ❌ Over-trusting substring matches ("Essence" appears in both but one is "Eye Essence" ≠ "Face Essence" → usually false; look for functional differences)
- ❌ Missing transliteration equivalence (兰蔻 vs Lancôme—MUST recognize as same brand, then compare product names carefully)
- ❌ Assuming tester/sample = different ("15ml tester" = "75ml full size" if same product name and brand → true)
- ❌ Confusing product line names with product names ("Estée Lauder Advanced Night Repair" line has multiple products: serum, eye cream, etc.—check core name)

EDGE CASES - Detailed Handling:
- Bundle products (e.g., "Skin Routine 3-pack" containing 3 different serums) should return FALSE—bundles are NOT single products. Only return TRUE if the bundled product has the exact same name as a standalone version.
- Seasonal/Limited Edition releases with identical core names ARE the same product (e.g., "Rose Essence Limited Edition 2024" = "Rose Essence" → true; seasonal descriptor does not change product identity).
- Tester/sample versions of the same product ARE the same (e.g., "Essence 15ml Tester" = "Essence 75ml Full Size" → true; size and tester status do not differentiate).
- Refill packs (e.g., "Cushion Refill Pack") = "Full Cushion Compact" → true if same product name and formula.
- Gift sets that bundle one named product (e.g., "Essence + Cream Gift Set") should be evaluated based on the primary product, not the bundle.
- Expired stock or different batch codes (e.g., "2023 batch" vs "2024 batch") with identical names ARE the same product (batch code does not create different products).
- PRE-LAUNCH/FUTURE RELEASE products with identical names are the same product regardless of availability date.

REQUIRED JSON RESPONSE FORMAT:
{
  "is_same_product": true or false,
  "confidence": 0.0 to 1.0 (float),
  "reasoning": "Single sentence summarizing the match decision and key reasoning"
}
Respond with JSON only, no markdown, no explanations outside JSON.
"""

# Module-level match cache (order-independent)
_match_cache: dict[str, "MatchResult"] = {}
_MATCH_CACHE_MAX = 1000

# Daily API call tracking
_daily_stats: dict[str, int] = {}  # {"2026-05-23": 42}


def _cache_key(name_a: str, name_b: str) -> str:
    """Create an order-independent cache key for two product names."""
    names = sorted([name_a.lower().strip(), name_b.lower().strip()])
    combined = "|".join(names)
    return hashlib.md5(combined.encode()).hexdigest()


def _track_api_call() -> None:
    """Track daily Claude API calls and warn if exceeding threshold."""
    today = datetime.date.today().isoformat()
    _daily_stats[today] = _daily_stats.get(today, 0) + 1
    count = _daily_stats[today]

    if count % 100 == 0:
        _logger.warning(
            "Claude matcher: %d API calls made today (%s). Monitor costs.",
            count,
            today,
        )
    if count > 500:
        _logger.warning(
            "Claude matcher: %d API calls today—EXCEEDS WARNING THRESHOLD (500). "
            "Implement rate limiting or batch processing urgently.",
            count,
        )

    # Clean up old dates (keep only today)
    for k in list(_daily_stats.keys()):
        if k != today:
            del _daily_stats[k]


class MatchResult(BaseModel):
    is_same_product: bool
    confidence: float
    reasoning: str


class ProductMatcher:
    def __init__(self) -> None:
        if not settings.use_local_ai:
            self._client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    def _quick_match(self, name_a: str, name_b: str) -> MatchResult | None:
        """규칙 기반 빠른 경로 (Claude 호출 없이)."""
        # 공백/특수문자 정규화
        norm_a = re.sub(r"[\s\-_]", "", name_a).lower()
        norm_b = re.sub(r"[\s\-_]", "", name_b).lower()

        # 1. 동일 문자열
        if norm_a == norm_b:
            return MatchResult(
                is_same_product=True,
                confidence=1.0,
                reasoning="Exact match after normalization",
            )

        # 2. 한쪽이 다른 쪽을 포함
        if len(norm_a) > 3 and len(norm_b) > 3:
            if norm_a in norm_b or norm_b in norm_a:
                return MatchResult(
                    is_same_product=True,
                    confidence=0.9,
                    reasoning="One name contains the other",
                )

        # 3. 원본 텍스트에서 단어 추출 (공백 제거 전 텍스트 사용)
        def extract_words(text: str) -> set[str]:
            lower = text.lower()
            english: set[str] = set(re.findall(r"[a-z]{3,}", lower))
            korean: set[str] = set(re.findall(r"[가-힣]{2,}", lower))
            return english | korean

        def dominant_script(words: set[str]) -> str:
            has_kor = any(re.search(r"[가-힣]", w) for w in words)
            has_eng = any(re.search(r"[a-z]", w) for w in words)
            if has_kor and not has_eng:
                return "korean"
            if has_eng and not has_kor:
                return "english"
            return "mixed"

        words_a = extract_words(name_a)
        words_b = extract_words(name_b)

        if not words_a or not words_b:
            return None  # 문자 정보 부족 → Claude에게 위임

        # 서로 다른 스크립트(한국어↔영어 등)이면 Claude에게 위임
        script_a = dominant_script(words_a)
        script_b = dominant_script(words_b)
        if script_a != script_b and "mixed" not in (script_a, script_b):
            return None

        common = words_a & words_b
        if not common:
            return MatchResult(
                is_same_product=False,
                confidence=0.9,
                reasoning="No common words between product names",
            )

        return None  # 공통 단어 있지만 불명확 → Claude에게 위임

    async def are_same_product(
        self,
        name_a: str,
        brand_a: str | None,
        name_b: str,
        brand_b: str | None,
    ) -> MatchResult:
        """두 제품명이 동일 제품인지 판단."""
        # 규칙 기반 빠른 경로
        quick_result = self._quick_match(name_a, name_b)
        if quick_result:
            return quick_result

        # Check cache before API call
        cache_key = _cache_key(name_a, name_b)
        if cache_key in _match_cache:
            return _match_cache[cache_key]

        # 로컬 또는 Claude API 호출
        # ja/zh 제품명을 영어로 번역 (로컬 AI 전용)
        if settings.use_local_ai:
            from app.ai.translator import translate_for_llm

            t_name_a = translate_for_llm(name_a)
            t_name_b = translate_for_llm(name_b)
            t_brand_a = translate_for_llm(brand_a) if brand_a else brand_a
            t_brand_b = translate_for_llm(brand_b) if brand_b else brand_b
        else:
            t_name_a = name_a
            t_name_b = name_b
            t_brand_a = brand_a
            t_brand_b = brand_b

        user_message = f"""Compare these two product names and determine if they refer to the same product:

Product A: "{t_name_a}"
Brand A: {t_brand_a or 'unknown'}

Product B: "{t_name_b}"
Brand B: {t_brand_b or 'unknown'}

Are they the same product?"""

        try:
            if settings.use_local_ai:
                # Ollama 로컬 모델 사용
                raw = await local_chat(_SYSTEM_PROMPT, user_message)
            else:
                # Claude API 사용
                if not settings.anthropic_api_key:
                    return MatchResult(
                        is_same_product=False,
                        confidence=0.0,
                        reasoning="API key not configured",
                    )

                _track_api_call()

                response = await self._client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=256,
                    system=[
                        {
                            "type": "text",
                            "text": _SYSTEM_PROMPT,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    messages=[{"role": "user", "content": user_message}],
                )

                raw = response.content[0].text.strip()

            # 공통 JSON 파싱 로직
            try:
                data = json.loads(raw)
                result = MatchResult(**data)
            except (json.JSONDecodeError, ValueError):
                # JSON 블록 안에 있을 경우 추출
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    data = json.loads(m.group())
                    result = MatchResult(**data)
                else:
                    raise

            # Store in cache (evict oldest if full)
            if len(_match_cache) >= _MATCH_CACHE_MAX:
                # Clear all cache when limit reached (simple strategy)
                _match_cache.clear()
            _match_cache[cache_key] = result

            return result

        except Exception as e:
            return MatchResult(
                is_same_product=False,
                confidence=0.0,
                reasoning=f"Matching failed: {str(e)}",
            )
