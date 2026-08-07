"""Celery task for matching cross-currency products."""
import asyncio
import uuid
from typing import Optional

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.matching import evaluate_match, containment_score
from app.ai.translator import translate_for_matching
from app.core.database import AsyncSessionLocal
from app.core.fx import convert
from app.core.size import sizes_match
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.models.product_match_candidate import ProductMatchCandidate
from app.tasks import celery


def match_pending_products(limit: int = 50) -> int:
    """Match pending orphan products to canonical products. Returns number matched."""
    return asyncio.run(_match_pending_products(limit))


match_pending_products = celery.task(match_pending_products)


async def _representative_size(db: AsyncSession, product_id: uuid.UUID) -> Optional[float]:
    """이 product에 달린 SaleEvent 중 size_ml이 있는 가장 최신 값 하나."""
    result = await db.execute(
        select(SaleEvent.size_ml)
        .where(
            SaleEvent.product_id == product_id,
            SaleEvent.size_ml.isnot(None),
            SaleEvent.deleted_at.is_(None),
        )
        .order_by(SaleEvent.created_at.desc())
        .limit(1)
    )
    row = result.fetchone()
    return row[0] if row else None


async def _candidate_sizes(db: AsyncSession, product_id: uuid.UUID) -> list[float]:
    """이 product에 달린 SaleEvent의 distinct size_ml(NULL 제외)."""
    result = await db.execute(
        select(func.distinct(SaleEvent.size_ml))
        .where(
            SaleEvent.product_id == product_id,
            SaleEvent.size_ml.isnot(None),
            SaleEvent.deleted_at.is_(None),
        )
    )
    return [row[0] for row in result.fetchall()]


async def _unit_price(
    db: AsyncSession, product_id: uuid.UUID, size_ml: float
) -> Optional[tuple[float, str]]:
    """해당 용량(sizes_match로 근접 판정)의 가장 최신 SaleEvent에서 (가격, 통화).
    없으면 None."""
    result = await db.execute(
        select(SaleEvent)
        .where(
            SaleEvent.product_id == product_id,
            SaleEvent.deleted_at.is_(None),
        )
        .order_by(func.abs(SaleEvent.size_ml - size_ml).asc())
        .limit(1)
    )
    event = result.scalar_one_or_none()
    if (
        event
        and event.sale_price
        and event.currency
        and sizes_match(event.size_ml, size_ml)
    ):
        return (float(event.sale_price), event.currency)
    return None


async def _match_orphan(db: AsyncSession, orphan: Product) -> None:
    """고아 1건을 처리 — 매칭되면 즉시 병합, 애매하면 candidate 행 생성, 후보
    없으면 아무것도 안 함(다음 배치가 다시 스캔)."""
    # 1. 번역
    try:
        translated = await asyncio.to_thread(
            translate_for_matching, str(orphan.name_jp), "ja"
        )
    except Exception:
        return  # 번역 실패 시 건너뜀
    if not translated:
        return

    # 2. 같은 브랜드 후보들
    result = await db.execute(
        select(Product)
        .where(
            func.lower(Product.brand) == func.lower(orphan.brand),
            Product.name_en.isnot(None),
            Product.deleted_at.is_(None),
        )
    )
    candidates = list(result.scalars().all())

    # 3. 고아 대표 용량
    orphan_size = await _representative_size(db, orphan.id)

    best_candidate: Product | None = None
    best_verdict: str | None = None
    best_key = (-1, -1.0)

    for candidate in candidates:
        candidate_sizes = await _candidate_sizes(db, candidate.id)

        matched_size = None
        if orphan_size and candidate_sizes:
            for size in candidate_sizes:
                if sizes_match(orphan_size, size):
                    matched_size = size
                    break

        canonical_unit_price = None
        orphan_unit_price_float = None
        if matched_size:
            unit_price = await _unit_price(db, candidate.id, matched_size)
            if unit_price:
                canonical_price, canonical_currency = unit_price
                if orphan_size:
                    orphan_unit_price = await _unit_price(db, orphan.id, orphan_size)
                    if orphan_unit_price:
                        orphan_price, orphan_currency = orphan_unit_price
                        if canonical_currency != orphan_currency:
                            converted_price = convert(
                                orphan_price, orphan_currency, canonical_currency
                            )
                            if converted_price is not None:
                                orphan_price = converted_price
                        orphan_unit_price_float = float(orphan_price / orphan_size)
                canonical_unit_price = canonical_price / matched_size

        verdict = evaluate_match(
            str(candidate.name_en),
            str(translated),
            canonical_size_ml=matched_size,
            listing_size_ml=orphan_size,
            canonical_unit_price=canonical_unit_price,
            listing_unit_price=orphan_unit_price_float,
        )
        if verdict == "reject":
            continue

        # (verdict 우선순위, containment_score) 튜플 비교 — match(1)이 needs_review(0)를
        # 이긴다. 점수가 살짝 높은 needs_review가 더 나은 match 후보를 밀어내면 이번
        # 배치에서 그 match 후보의 candidate 행 자체가 안 생긴다(적대감사 R1 반영).
        candidate_key = (
            1 if verdict == "match" else 0,
            float(containment_score(str(candidate.name_en), str(translated))),
        )
        if candidate_key > best_key:
            best_candidate = candidate
            best_verdict = verdict
            best_key = candidate_key

    best_score = best_key[1]

    # 5. 최종 처리
    if best_candidate:
        try:
            candidate_row = ProductMatchCandidate(
                orphan_product_id=orphan.id,
                canonical_product_id=best_candidate.id,
                score=best_score,
                status="approved" if best_verdict == "match" else "pending",
                decided_at=func.now() if best_verdict == "match" else None,
                decided_by="auto" if best_verdict == "match" else None,
            )
            db.add(candidate_row)
            await db.flush()
        except Exception:
            await db.rollback()
            return  # 다른 worker가 먼저 처리함

        if best_verdict == "match":
            # canonical 행에 락 걸고 병합
            locked_canonical = (
                await db.execute(
                    select(Product)
                    .where(Product.id == best_candidate.id)
                    .with_for_update()
                )
            ).scalar_one()
            await _merge_products(db, orphan, locked_canonical)


async def _merge_products(db: AsyncSession, orphan: Product, canonical: Product) -> None:
    """orphan을 canonical에 병합.

    orphan.deleted_at을 먼저 찍는다 — canonical에 orphan의 name_jp/kr/cn을 backfill하면
    그 순간 orphan과 canonical이 (name_jp, brand) 또는 (name_en, brand) 파셜 유니크
    인덱스 값이 같아지는데, orphan이 아직 active(deleted_at NULL)면 autoflush 시점에
    제약 위반이 난다(실측: 리뷰 중 재현).
    """
    orphan.deleted_at = func.now()
    await db.flush()  # 파셜 유니크 인덱스는 DEFERRABLE이 아니다 — autoflush 배치 순서에
    # 기대지 않고 orphan을 먼저 확정 커밋해야 canonical의 name_jp/kr/cn backfill이
    # 같은 문장 안에서 제약을 안 밟는다.

    if orphan.name_jp and not canonical.name_jp:
        canonical.name_jp = orphan.name_jp
    if orphan.name_kr and not canonical.name_kr:
        canonical.name_kr = orphan.name_kr
    if orphan.name_cn and not canonical.name_cn:
        canonical.name_cn = orphan.name_cn

    await db.execute(
        update(SaleEvent)
        .where(SaleEvent.product_id == orphan.id)
        .values(product_id=canonical.id)
    )


async def _match_pending_products(limit: int = 50) -> int:
    """고아 선별 및 매칭."""
    async with AsyncSessionLocal() as db:
        # 고아 선별: LEFT JOIN, NOT IN 쓰지 마라
        result = await db.execute(
            select(Product)
            .outerjoin(
                ProductMatchCandidate,
                Product.id == ProductMatchCandidate.orphan_product_id,
            )
            .where(
                Product.name_en.is_(None),
                Product.name_jp.isnot(None),
                Product.deleted_at.is_(None),
                Product.brand.isnot(None),
                ProductMatchCandidate.id.is_(None),
            )
            .limit(limit)
        )
        orphans = list(result.scalars().all())

        count = 0
        for orphan in orphans:
            try:
                await _match_orphan(db, orphan)
                count += 1
            except Exception:
                continue  # 개별 실패가 배치를 안 죽임

        await db.commit()
        return count