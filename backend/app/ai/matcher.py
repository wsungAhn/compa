"""Cross-country product matching — unify product names across KR/US/JP/CN."""
import json
import re
from typing import Any

import anthropic
from sqlalchemy import func, or_, select
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

    # Stage 1: Exact match (case-insensitive)
    # Use func.lower for SQL-side normalization, but we also normalize candidates
    result = await db.execute(
        select(Product).where(
            Product.deleted_at.is_(None),
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
        brand_candidates = [
            c for c in candidates
            if c.brand and c.brand.lower() == brand_lower
        ]

        if len(brand_candidates) == 1:
            return brand_candidates[0]

        # Stage 3: Claude fallback (if multiple brand candidates)
        if len(brand_candidates) > 1 and settings.anthropic_api_key:
            matched = await _ask_claude_for_match(name, brand, country, brand_candidates)
            if matched:
                return matched

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
    except Exception:
        # On any error, return None (defensive)
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
    await db.flush()
    return product
