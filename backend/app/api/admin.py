"""Admin API for managing product match candidates."""
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update, func

from app.api.feedback import _is_authorized_feedback_secret
from app.core.database import AsyncSessionLocal
from app.models.product import Product
from app.models.product_match_candidate import ProductMatchCandidate
from app.tasks.match_products import _merge_products, orphan_product_filters

router = APIRouter(tags=["admin"])
_logger = logging.getLogger(__name__)

ORPHAN_SAMPLE_LIMIT = 8


class ProductMatchCandidateOut(BaseModel):
    id: uuid.UUID
    orphan_product_id: uuid.UUID
    orphan_name: Optional[str]  # orphan.name_jp
    canonical_product_id: uuid.UUID
    canonical_name: Optional[str]  # canonical.name_en
    brand: Optional[str]
    score: float
    status: str
    created_at: datetime
    model_config = {"from_attributes": False}  # 수동 조립(조인 결과라 ORM 모델 하나가 아님)


class CoverageOrphanOut(BaseModel):
    brand: Optional[str]
    name: Optional[str]
    source_country: str
    unmatched_days: int


class CoverageOut(BaseModel):
    total_count: int
    matched_count: int
    orphan_count: int
    coverage_pct: float
    orphans: list[CoverageOrphanOut]


def _unmatched_days(created_at: datetime, now: datetime) -> int:
    created_at_utc = (
        created_at.replace(tzinfo=timezone.utc)
        if created_at.tzinfo is None
        else created_at.astimezone(timezone.utc)
    )
    return max((now - created_at_utc).days, 0)


@router.get("/api/admin/product-matches", response_model=list[ProductMatchCandidateOut])
async def list_product_matches(
    status: str = "pending",
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
) -> list[ProductMatchCandidateOut]:
    if not _is_authorized_feedback_secret(x_admin_secret):
        raise HTTPException(status_code=404, detail="Not found")
    
    async with AsyncSessionLocal() as db:
        # ProductMatchCandidate + orphan Product + canonical Product 조인
        from sqlalchemy import alias
        
        orphan_alias = alias(Product.__table__)
        canonical_alias = alias(Product.__table__)
        
        query = (
            select(
                ProductMatchCandidate,
                orphan_alias.c.name_jp.label("orphan_name"),
                canonical_alias.c.name_en.label("canonical_name"),
                orphan_alias.c.brand.label("brand"),
            )
            .join(
                orphan_alias,
                ProductMatchCandidate.orphan_product_id == orphan_alias.c.id,
            )
            .join(
                canonical_alias,
                ProductMatchCandidate.canonical_product_id == canonical_alias.c.id,
            )
            .where(ProductMatchCandidate.status == status)
            .order_by(ProductMatchCandidate.created_at.desc())
        )
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        candidates = []
        for row in rows:
            candidate, orphan_name, canonical_name, brand = row
            candidates.append(
                ProductMatchCandidateOut(
                    id=candidate.id,
                    orphan_product_id=candidate.orphan_product_id,
                    orphan_name=orphan_name,
                    canonical_product_id=candidate.canonical_product_id,
                    canonical_name=canonical_name,
                    brand=brand,
                    score=candidate.score,
                    status=candidate.status,
                    created_at=candidate.created_at,
                )
            )
        
        return candidates


@router.get("/api/admin/coverage", response_model=CoverageOut)
async def get_coverage(
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
) -> CoverageOut:
    if not _is_authorized_feedback_secret(x_admin_secret):
        raise HTTPException(status_code=404, detail="Not found")

    try:
        async with AsyncSessionLocal() as db:
            total_count = (
                await db.execute(
                    select(func.count()).select_from(Product).where(Product.deleted_at.is_(None))
                )
            ).scalar_one()
            orphan_count = (
                await db.execute(
                    select(func.count())
                    .select_from(Product)
                    .where(*orphan_product_filters())
                )
            ).scalar_one()
            orphan_rows = (
                await db.execute(
                    select(Product)
                    .where(*orphan_product_filters())
                    .order_by(Product.created_at.asc())
                    .limit(ORPHAN_SAMPLE_LIMIT)
                )
            ).scalars().all()
    except Exception as exc:
        _logger.exception("coverage query failed: %s", type(exc).__name__)
        raise HTTPException(status_code=500, detail="Coverage query failed") from exc

    matched_count = int(total_count) - int(orphan_count)
    coverage_pct = 0.0
    if total_count:
        coverage_pct = round((matched_count / int(total_count)) * 100, 1)

    now = datetime.now(timezone.utc)
    return CoverageOut(
        total_count=int(total_count),
        matched_count=matched_count,
        orphan_count=int(orphan_count),
        coverage_pct=coverage_pct,
        orphans=[
            CoverageOrphanOut(
                brand=product.brand,
                name=product.name_jp,
                source_country="JP",
                unmatched_days=_unmatched_days(product.created_at, now),
            )
            for product in orphan_rows
        ],
    )


@router.post("/api/admin/product-matches/{candidate_id}/approve")
async def approve_product_match(
    candidate_id: uuid.UUID,
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
) -> dict[str, bool]:
    if not _is_authorized_feedback_secret(x_admin_secret):
        raise HTTPException(status_code=404, detail="Not found")
    
    async with AsyncSessionLocal() as db:
        # 승인 후 실제 병합 수행 — orphan/canonical Product를 불러와 _merge_products 재사용
        result = await db.execute(
            update(ProductMatchCandidate)
            .where(
                ProductMatchCandidate.id == candidate_id,
                ProductMatchCandidate.status == "pending",
            )
            .values(
                status="approved",
                decided_at=datetime.now(timezone.utc),
                decided_by="admin",
            )
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Already decided or not found")
        
        # 실제 병합 수행
        row = await db.execute(
            select(ProductMatchCandidate).where(ProductMatchCandidate.id == candidate_id)
        )
        candidate = row.scalar_one()
        
        orphan = await db.execute(
            select(Product).where(Product.id == candidate.orphan_product_id)
        )
        orphan_product = orphan.scalar_one()
        
        canonical = await db.execute(
            select(Product)
            .where(Product.id == candidate.canonical_product_id)
            .with_for_update()
        )
        canonical_product = canonical.scalar_one()
        
        await _merge_products(db, orphan_product, canonical_product)
        await db.commit()
    
    return {"ok": True}


@router.post("/api/admin/product-matches/{candidate_id}/reject")
async def reject_product_match(
    candidate_id: uuid.UUID,
    x_admin_secret: Optional[str] = Header(default=None, alias="X-Admin-Secret"),
) -> dict[str, bool]:
    if not _is_authorized_feedback_secret(x_admin_secret):
        raise HTTPException(status_code=404, detail="Not found")
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(ProductMatchCandidate)
            .where(
                ProductMatchCandidate.id == candidate_id,
                ProductMatchCandidate.status == "pending",
            )
            .values(
                status="rejected",
                decided_at=datetime.now(timezone.utc),
                decided_by="admin",
            )
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=409, detail="Already decided or not found")
        
        await db.commit()
    
    return {"ok": True}
