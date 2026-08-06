# LLM 입력 최적화용 ja/zh → en 번역 유틸리티
import logging
import re
from typing import Optional

import httpx

from app.core.config import settings
from app.scrapers.brand_dictionary import canonicalize_brand_mentions

_logger = logging.getLogger(__name__)

# 인메모리 캐시 (maxsize 1000)
_translation_cache: dict[str, str] = {}
_CACHE_MAX_SIZE = 1000

_LANG_NAMES = {"ja": "Japanese", "zh": "Chinese", "ko": "Korean"}

_LATIN_RE = re.compile(r"[A-Za-z]")


def _build_translate_prompt(text: str, source_lang: str) -> str:
    """실측으로 검증된 정형 프롬프트. 임의로 문구를 바꾸지 마라 — 나이브한 프롬프트는
    수다스러운 잡담체 응답을 낸다(실측: "Translate to English: ...로 물으면 옵션
    3개를 늘어놓는 답이 옴).
    """
    lang_name = _LANG_NAMES.get(source_lang, source_lang)
    return (
        f"You are a professional {lang_name} ({source_lang}) to English (en) translator. "
        "Your goal is to accurately convey the meaning and nuances of the original "
        f"{lang_name} text while adhering to English grammar, vocabulary, and cultural "
        "sensitivities. Produce only the English translation, without any additional "
        "explanations or commentary.\n\n"
        f"Please translate the following {lang_name} text into English:\n\n{text}"
    )


def _call_translategemma(text: str, source_lang: str) -> str | None:
    """실패 시 None(예외 전파 금지 — CLAUDE.md 절대 규칙). 랩탑이 꺼져있어도 서비스가
    안 죽어야 한다."""
    try:
        response: httpx.Response = httpx.post(
            f"{settings.translation_ollama_url}/api/generate",
            json={
                "model": settings.local_translation_model,
                "prompt": _build_translate_prompt(text, source_lang),
                "stream": False,
            },
            timeout=60.0,
        )
        
        if response.status_code != 200:
            _logger.warning(
                f"Translation API returned status {response.status_code} for text: {text[:50]}..."
            )
            return None

        result = response.json()
        translated: str = str(result.get("response", "")).strip()

        if not translated:
            return None

        return translated

    except (httpx.HTTPError, ValueError) as e:
        # ValueError covers response.json()의 JSONDecodeError — 응답 바디가 깨진 경우도
        # 예외를 밖으로 새게 두면 안 된다(실측: 랩탑이 재기동 중이면 빈/HTML 응답이 옴).
        _logger.warning(f"Translation API error for text: {text[:50]}... Error: {e}")
        return None


def _looks_like_translation_failure(original: str, translated: str, source_lang: str) -> bool:
    """번역 실패를 감지한다(적대감사 R2). 최소 검사 둘: 출력이 입력과 같으면(=번역이
    안 된 것) 실패, CJK 입력인데 출력에 라틴 문자가 하나도 없으면(=번역이 원문을
    그대로 반복했거나 이상한 응답) 실패로 본다.
    """
    if not translated or translated == original:
        return True
        
    if source_lang in ("ja", "zh", "ko") and not _LATIN_RE.search(translated):
        return True
        
    return False


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
    """핵심 함수: ja/zh → en 번역. 실패하거나 en/ko면 원문 그대로 반환(예외 전파 금지).
    LLM 입력 전처리용 — 최선 노력이면 충분하고, 실패해도 서비스가 죽으면 안 된다.
    """
    if not text:
        return text or ""

    if text in _translation_cache:
        return _translation_cache[text]

    lang = detect_language(text)
    if lang not in ("ja", "zh"):
        return text

    translated = _call_translategemma(text, lang)
    if translated is None or _looks_like_translation_failure(text, translated, lang):
        _logger.warning(
            f"Translation failed for text: {text[:50]}... (lang={lang}). "
            f"Returning original text."
        )
        return text

    if len(_translation_cache) >= _CACHE_MAX_SIZE:
        _translation_cache.clear()
    _translation_cache[text] = translated
    return translated


def translate_for_matching(text: str, source_lang: str) -> str | None:
    """크로스 통화 매칭 전용. 실패 시 None — 호출부(D단계)가 매칭을 시도하지 않아야
    한다는 신호다. 번역 전에 브랜드 별칭을 정본화한다(실측: 일반 번역이 "토리든"을
    "Tori Den"/"Toryden"으로 비결정적으로 오역해 포함도 매칭이 깨진다).
    """
    if not text:
        return None

    canonical_text = canonicalize_brand_mentions(text)
    translated = _call_translategemma(canonical_text, source_lang)
    if translated is None or _looks_like_translation_failure(canonical_text, translated, source_lang):
        return None
        
    return translated
