"""Social post processing pipeline — extraction → matching → SaleEvent creation."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.classifier import classify_rule_based
from app.ai.extractor import SocialExtractor
from app.ai.matcher import get_or_create_product
from app.core.config import settings
from app.models.platform import Platform
from app.models.sale_event import SaleEvent
from app.models.social_post import SocialPost

# Currency to country code mapping
CURRENCY_TO_COUNTRY: dict[str, str] = {
    "KRW": "KR",
    "USD": "US",
    "JPY": "JP",
    "CNY": "CN",
}

# SocialPost.platform enum values to Platform.name mapping
SOCIAL_PLATFORM_NAME: dict[str, str] = {
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "facebook": "Facebook",
    "naver_blog": "네이버블로그",
    "xiaohongshu": "小红书",
}


def infer_country(extracted_currency: str | None, social_platform: str) -> str:
    """Infer country from currency or platform fallback.

    Args:
        extracted_currency: Currency code from extraction (KRW, USD, JPY, CNY)
        social_platform: Platform enum value (instagram, tiktok, facebook, naver_blog, xiaohongshu)

    Returns:
        2-letter country code (KR, US, JP, CN), defaults to KR
    """
    if extracted_currency and extracted_currency in CURRENCY_TO_COUNTRY:
        return CURRENCY_TO_COUNTRY[extracted_currency]

    if social_platform == "naver_blog":
        return "KR"

    return "KR"


def match_event_to_post(event_product_name: str, posts: list[tuple[int, str]]) -> int:
    """Match extracted event to the post that contains its product name.

    Args:
        event_product_name: Product name from extracted event
        posts: List of (index, content) tuples from SocialPost batch

    Returns:
        Index of the matched post in the original batch; if no match, returns first index (0)
    """
    if not posts:
        return 0

    product_name_lower = event_product_name.lower()
    for idx, content in posts:
        if product_name_lower in content.lower():
            return idx

    # Fallback to first post
    return posts[0][0]


async def process_social_posts(db: AsyncSession, limit: int = 20) -> int:
    """Process unprocessed social posts: extract → match → create SaleEvents.

    Args:
        db: Database session
        limit: Maximum number of posts to process in this call

    Returns:
        Number of SaleEvents created
    """
    # Fetch unprocessed social posts
    result = await db.execute(
        select(SocialPost)
        .where(
            SocialPost.processed.is_(False),
            SocialPost.content.isnot(None),
        )
        .order_by(SocialPost.created_at)
        .limit(limit)
    )
    posts: list[SocialPost] = list(result.scalars().all())

    if not posts or not settings.anthropic_api_key:
        return 0

    # Extract events from post contents
    post_contents = [p.content for p in posts if p.content]
    extractor = SocialExtractor()
    extracted_events = await extractor.extract_batch(post_contents)

    # Track posts with indices for matching
    posts_with_indices: list[tuple[int, str]] = [
        (i, p.content or "") for i, p in enumerate(posts)
    ]

    event_count = 0
    for extracted_event in extracted_events:
        try:
            # Match event to post
            matched_post_idx = match_event_to_post(
                extracted_event.product_name, posts_with_indices
            )
            matched_post = posts[matched_post_idx]

            # Infer country
            country = infer_country(extracted_event.currency, matched_post.platform)

            # Get or create product
            product = await get_or_create_product(
                db,
                extracted_event.product_name,
                extracted_event.brand,
                country,
            )

            # Look up platform by name
            platform_name = SOCIAL_PLATFORM_NAME.get(matched_post.platform)
            if not platform_name:
                continue

            platform_result = await db.execute(
                select(Platform).where(Platform.name == platform_name)
            )
            platform = platform_result.scalar_one_or_none()
            if not platform:
                continue

            # Classify event type
            event_type_result = classify_rule_based(
                extracted_event.event_name,
                extracted_event.reason,
                extracted_event.start_date,
            )
            event_type = event_type_result.event_type if event_type_result else None

            # Create SaleEvent
            sale_event = SaleEvent(
                product_id=product.id,
                platform_id=platform.id,
                event_name=extracted_event.event_name,
                event_type=event_type,
                start_date=extracted_event.start_date,
                end_date=extracted_event.end_date,
                original_price=(
                    float(extracted_event.original_price)
                    if extracted_event.original_price is not None
                    else None
                ),
                sale_price=(
                    float(extracted_event.sale_price)
                    if extracted_event.sale_price is not None
                    else None
                ),
                discount_rate=(
                    float(extracted_event.discount_rate)
                    if extracted_event.discount_rate is not None
                    else None
                ),
                currency=extracted_event.currency,
                reason=extracted_event.reason,
                source_url=matched_post.post_url,
                confidence=extracted_event.confidence,
                needs_review=extracted_event.needs_review,
                raw_text=(
                    matched_post.content[:1000]
                    if matched_post.content
                    else None
                ),
            )
            db.add(sale_event)

            # Link post to event
            matched_post.sale_event_id = sale_event.id
            event_count += 1

        except Exception:
            # Per spec: swallow exceptions, don't propagate
            continue

    # Mark all processed posts
    for post in posts:
        post.processed = True

    # Commit once at the end
    await db.commit()

    return event_count
