"""Cross-country product matching — unify product names across KR/US/JP/CN."""
import json
import logging
import re
from typing import Any

import anthropic

_logger = logging.getLogger(__name__)
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.product import Product

# Country code to Product column name mapping
COUNTRY_NAME_COLUMN: dict[str, str] = {
    "KR": "name_kr",
    "US": "name_en",
    "JP": "name_jp",
    "CN": "name_cn",
}


def normalize_name(name: str) -> str:
    """Normalize product name for comparison.

    - Remove HTML tags (e.g. <b>, <i>)
    - Convert to lowercase
    - Collapse repeated whitespace to single space
    - Strip leading/trailing whitespace

    Args:
        name: Raw product name

    Returns:
        Normalized name
    """
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", "", name)
    # Convert to lowercase
    cleaned = cleaned.lower()
    # Collapse repeated whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)
    # Strip
    cleaned = cleaned.strip()
    return cleaned


_NAME_STOPWORDS = {
    "the", "and", "for", "with", "set", "kit", "duo", "new", "mini",
    "oz", "ml", "size", "value", "official", "official)",
}


def _name_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^\w가-힣ぁ-んァ-ン一-龥]+", " ", text.lower())
    return {w for w in cleaned.split() if len(w) > 2 and w not in _NAME_STOPWORDS}


# 제품 종류. 종류가 다르면 이름이 아무리 겹쳐도 같은 제품이 아니다
# ("Facial Treatment Essence"와 "Facial Treatment Mask"는 3토큰을 공유한다).
_PRODUCT_TYPES = {
    "essence", "serum", "ampoule", "cream", "lotion", "toner", "mask", "cleanser",
    "oil", "balm", "sunscreen", "spf", "cushion", "foundation", "lipstick", "tint",
    "shampoo", "conditioner", "mist", "emulsion", "gel", "scrub", "peel", "patch",
    "에센스", "세럼", "앰플", "크림", "로션", "토너", "마스크", "클렌저", "쿠션",
}


def _types_in(tokens: set[str]) -> set[str]:
    return tokens & _PRODUCT_TYPES


def _same_product_evidence(candidate: Product, normalized_input: str) -> bool:
    """후보와 같은 제품으로 볼 근거가 있는가.

    브랜드 일치만으로 합치면 카탈로그가 무너진다(2026-08-06 실측: SK-II 8개 제품이
    한 행으로). 여기서는 두 가지만 본다 — 종류가 다르면 거부, 그리고 이름 토큰이
    충분히 겹칠 것. 정교한 매칭(번역·용량·포함도)은 크로스 통화 계획 B단계 담당이다.
    """
    incoming = _name_tokens(normalized_input)
    if not incoming:
        return False
    incoming_types = _types_in(incoming)

    for column in COUNTRY_NAME_COLUMN.values():
        value = getattr(candidate, column, None)
        if not value:
            continue
        existing = _name_tokens(str(value))
        if not existing:
            continue
        existing_types = _types_in(existing)
        # 양쪽 다 종류를 밝혔는데 다르면 같은 제품이 아니다.
        if incoming_types and existing_types and not (incoming_types & existing_types):
            continue
        shared = incoming & existing
        if not shared:
            continue
        smaller = min(len(incoming), len(existing))
        if len(shared) >= 2 and smaller and len(shared) / smaller >= 0.5:
            return True
        # 한쪽 이름이 토큰 하나뿐이면 그 토큰이 곧 정체성이다("윤조에센스").
        # 다만 짧은 일반어("oil", "set")가 이 예외를 타면 안 되므로 길이를 요구한다.
        if smaller == 1 and max(len(w) for w in shared) >= 4:
            return True
    return False


async def find_matching_product(
    db: AsyncSession,
    name: str,
    brand: str | None,
    country: str,
) -> Product | None:
    """Find an existing product that matches the given name, brand, and country.

    Matching strategy:
    1. Exact match: normalized input name vs normalized country column value
    2. Brand match: if brand is set, fetch candidates with same brand (case-insensitive)
       If exactly one candidate exists, return it (cross-language heuristic)
    3. Claude fallback: if multiple brand candidates, ask Claude to disambiguate

    Args:
        db: Database session
        name: Normalized product name
        brand: Product brand (optional)
        country: 2-letter country code (KR, US, JP, CN)

    Returns:
        Matched Product or None
    """
    column_name = COUNTRY_NAME_COLUMN.get(country)
    if not column_name:
        return None

    normalized_input = normalize_name(name)

    country_column = getattr(Product, column_name)

    # Stage 1: Exact match (case-insensitive), with DB-side candidate narrowing.
    result = await db.execute(
        select(Product).where(
            Product.deleted_at.is_(None),
            func.lower(country_column) == normalized_input,
        )
    )
    candidates = list(result.scalars().all())

    # Check exact match by comparing normalized values
    for candidate in candidates:
        col_value = getattr(candidate, column_name)
        if col_value and normalize_name(col_value) == normalized_input:
            return candidate

    # Stage 2: Brand match (if brand is provided)
    if brand:
        brand_lower = brand.lower()
        result = await db.execute(
            select(Product).where(
                Product.deleted_at.is_(None),
                Product.brand.is_not(None),
                func.lower(Product.brand) == brand_lower,
            )
        )
        brand_candidates = [
            c for c in result.scalars().all()
            if c.brand and c.brand.lower() == brand_lower
        ]

        for candidate in brand_candidates:
            col_value = getattr(candidate, column_name)
            if col_value and normalize_name(col_value) == normalized_input:
                return candidate

        if len(brand_candidates) == 1:
            # 브랜드만 같다고 같은 제품이 아니다. 이 지름길은 브랜드에 제품이 하나
            # 생기는 순간 **그 브랜드의 모든 신규 제품을 그 하나로 빨아들인다**
            # (2026-08-06 실측: SK-II 공홈의 SKINPOWER·LXP·Cleanser·Mask·Essence가
            # 전부 한 행으로 합쳐졌다). 이름에 최소한의 근거가 있을 때만 채택한다.
            if _same_product_evidence(brand_candidates[0], normalized_input):
                return brand_candidates[0]

        # Stage 3: Claude fallback (if multiple brand candidates)
        if len(brand_candidates) > 1 and settings.anthropic_api_key:
            matched = await _ask_claude_for_match(name, brand, country, brand_candidates)
            if matched:
                return matched
    else:
        # Fallback for stored raw scraped names that differ after normalization
        # (HTML tags, repeated whitespace), while still avoiding rows without the
        # country-specific name.
        result = await db.execute(
            select(Product).where(
                Product.deleted_at.is_(None),
                country_column.is_not(None),
            )
        )
        candidates = list(result.scalars().all())

        for candidate in candidates:
            col_value = getattr(candidate, column_name)
            if col_value and normalize_name(col_value) == normalized_input:
                return candidate

    return None


async def _ask_claude_for_match(
    name: str,
    brand: str,
    country: str,
    candidates: list[Product],
) -> Product | None:
    """Ask Claude to disambiguate which candidate matches the given product.

    Args:
        name: Product name
        brand: Product brand
        country: Country code
        candidates: List of candidate products with matching brand

    Returns:
        Matched Product or None
    """
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Format candidates for Claude
    candidates_text = "\n".join(
        f"- id={c.id}, name_kr={c.name_kr}, name_en={c.name_en}, "
        f"name_jp={c.name_jp}, name_cn={c.name_cn}, brand={c.brand}"
        for c in candidates
    )

    prompt = f"""Given a product found on {country} platform, determine which candidate product it matches.

Input product:
- name: {name}
- brand: {brand}
- country: {country}

Candidate products in database:
{candidates_text}

Respond with JSON only: {{"match_id": "<uuid or null>"}}
If none matches, return {{"match_id": null}}.
If input is ambiguous, return {{"match_id": null}}."""

    try:
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text response
        text_content = ""
        for block in response.content:
            if isinstance(block, anthropic.types.TextBlock):
                text_content = block.text.strip()
                break

        if not text_content:
            return None

        # Parse JSON response
        data: Any = json.loads(text_content)
        match_id = data.get("match_id")

        if match_id:
            # Find candidate by UUID
            for c in candidates:
                if str(c.id) == match_id:
                    return c

        return None
    except anthropic.APIError as exc:
        # API 실패와 "매칭 없음"이 둘 다 조용한 None이라, 크레딧 소진 중 400이
        # 매 이벤트 신규 상품 생성(=중복)으로 둔갑해도 로그 한 줄 없었다
        # (08-08 실측 382회). 동작은 보수적 유지(병합 안 함) — 침묵만 금지.
        _logger.warning(
            "Claude match unavailable (%s): creating unmatched product for name=%s brand=%s",
            type(exc).__name__, name, brand,
        )
        return None
    except Exception:
        # 응답 파싱 실패(JSON 아님 등) — 매칭 포기, 신규 생성으로 폴백
        _logger.warning("Claude match response unparseable for name=%s brand=%s", name, brand)
        return None


async def get_or_create_product(
    db: AsyncSession,
    name: str,
    brand: str | None,
    country: str,
) -> Product:
    """Get existing product or create a new one.

    Matching logic:
    - If existing product found: update its country-specific name column (if empty) and return
    - If not found: create new Product with only the country-specific name column set

    Args:
        db: Database session
        name: Product name (raw, not normalized)
        brand: Product brand (optional)
        country: 2-letter country code (KR, US, JP, CN)

    Returns:
        Product (existing or newly created)
    """
    column_name = COUNTRY_NAME_COLUMN.get(country)
    if not column_name:
        # Fallback: create with name_en if country is invalid
        column_name = "name_en"

    # Try to find existing product
    matched = await find_matching_product(db, name, brand, country)

    if matched:
        # Update country-specific column if empty
        current_value = getattr(matched, column_name)
        if not current_value:
            setattr(matched, column_name, name)
            await db.flush()
        return matched

    # Create new product
    kwargs: dict[str, Any] = {
        "brand": brand,
        column_name: name,
    }
    product = Product(**kwargs)
    db.add(product)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        matched = await find_matching_product(db, name, brand, country)
        if matched:
            return matched
        raise
    return product
