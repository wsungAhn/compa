# LLM 입력 최적화용 ja/zh → en 번역 유틸리티
import logging
from typing import Optional

from deep_translator import GoogleTranslator

_logger = logging.getLogger(__name__)

# 인메모리 캐시 (maxsize 1000)
_translation_cache: dict[str, str] = {}
_CACHE_MAX_SIZE = 1000


def detect_language(text: str) -> str:
    """유니코드 문자 비율로 언어 감지.

    - Hiragana (U+3040-U+309F) / Katakana (U+30A0-U+30FF) 20%+ → "ja"
    - CJK (U+4E00-U+9FFF) 20%+ → "zh" (단, ja 판정 우선)
    - 한글 (U+AC00-U+D7AF) → "ko"
    - 나머지 → "en"
    """
    if not text:
        return "en"

    hiragana_katakana_count = sum(
        1 for c in text if (0x3040 <= ord(c) <= 0x309F or 0x30A0 <= ord(c) <= 0x30FF)
    )
    cjk_count = sum(1 for c in text if 0x4E00 <= ord(c) <= 0x9FFF)
    korean_count = sum(1 for c in text if 0xAC00 <= ord(c) <= 0xD7AF)

    total_chars = len(text)

    # Hiragana/Katakana 20%+ → ja (우선)
    if hiragana_katakana_count / total_chars >= 0.2:
        return "ja"

    # CJK 20%+ → zh
    if cjk_count / total_chars >= 0.2:
        return "zh"

    # 한글 감지 → ko
    if korean_count > 0:
        return "ko"

    return "en"


def translate_for_llm(text: Optional[str]) -> str:
    """핵심 함수: ja/zh → en 번역.

    - 빈 문자열 / None → 그대로 반환
    - detect_language 호출 → ja/zh만 번역, 나머지는 원문 반환
    - GoogleTranslator(source="auto", target="en").translate(text) 사용
    - 인메모리 캐시 dict (maxsize 1000, 초과 시 clear)
    - try/except로 감싸고 실패 시 원문 반환 + warning 로그
    """
    if not text:
        return text or ""

    # 캐시 확인
    if text in _translation_cache:
        return _translation_cache[text]

    # 언어 감지
    lang = detect_language(text)

    # ja/zh가 아니면 원문 반환
    if lang not in ("ja", "zh"):
        return text

    # ja/zh이면 번역 시도
    try:
        translator = GoogleTranslator(source="auto", target="en")
        translated = translator.translate(text)

        # 캐시 저장 (초과 시 clear)
        if len(_translation_cache) >= _CACHE_MAX_SIZE:
            _translation_cache.clear()
        _translation_cache[text] = translated

        return translated
    except Exception as e:
        _logger.warning(
            f"Translation failed for text: {text[:50]}... (lang={lang}). "
            f"Error: {e}. Returning original text."
        )
        return text
