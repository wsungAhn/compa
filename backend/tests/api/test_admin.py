"""Tests for admin API endpoints."""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.admin import router
from app.core.config import settings
from app.core.database import engine
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.models.product_match_candidate import ProductMatchCandidate


@pytest.fixture
async def client():
    """httpx.AsyncClient(ASGITransport) — sync TestClient는 별도 스레드/이벤트루프를 써서
    db_session과 같은 커넥션 풀을 공유하면 asyncpg가 깨진다(실측: "attached to a
    different loop"). ASGITransport는 테스트와 같은 이벤트 루프에서 돈다."""
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
async def _dispose_engine():
    """asyncpg 커넥션은 생성된 이벤트 루프에 묶인다 — 테스트마다 풀을 비운다."""
    yield
    await engine.dispose()


@pytest.fixture
async def db_session() -> AsyncSession:
    """Database session fixture."""
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def platform_id(db_session: AsyncSession) -> uuid.UUID:
    """SaleEvent.platform_id는 NOT NULL FK다 — 시딩된 기존 Platform 하나를 재사용한다."""
    from app.models.platform import Platform

    result = await db_session.execute(select(Platform.id).limit(1))
    return result.scalar_one()


@pytest.fixture
async def cleanup_db(db_session: AsyncSession):
    """Clean up test data after each test."""
    yield
    # Clean up all test data
    await db_session.execute(update(ProductMatchCandidate).values(status="rejected"))
    await db_session.execute(update(Product).where(Product.name_jp.like("SK-II%")).values(deleted_at=func.now()))
    await db_session.commit()


@pytest.fixture
def admin_secret():
    """Admin secret fixture."""
    original = settings.admin_secret
    settings.admin_secret = "test-admin-secret"
    yield "test-admin-secret"
    settings.admin_secret = original


async def test_list_product_matches_unauthorized(client):
    """Test list product matches without admin secret."""
    response = await client.get("/api/admin/product-matches")
    assert response.status_code == 404


async def test_list_product_matches_authorized(client, admin_secret):
    """Test list product matches with admin secret."""
    response = await client.get("/api/admin/product-matches", headers={"X-Admin-Secret": admin_secret})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_list_product_matches_with_status(client, admin_secret):
    """Test list product matches with specific status."""
    response = await client.get(
        "/api/admin/product-matches?status=pending",
        headers={"X-Admin-Secret": admin_secret}
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_approve_product_match(client, admin_secret, db_session, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test approving a product match."""
    # Create canonical product
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    await db_session.flush()
    
    # Create orphan product
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.flush()
    
    # Create candidate
    candidate = ProductMatchCandidate(
        orphan_product_id=orphan_product.id,
        canonical_product_id=canonical_product.id,
        score=0.9,
        status="pending",
    )
    db_session.add(candidate)
    await db_session.commit()
    candidate_id = candidate.id

    # Approve
    response = await client.post(
        f"/api/admin/product-matches/{candidate_id}/approve",
        headers={"X-Admin-Secret": admin_secret}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    # 승인은 엔드포인트가 자체 세션에서 커밋한다 — 이 테스트의 db_session identity map은
    # 그 변경을 모른다, expire해서 다시 읽는다.
    db_session.expire_all()

    # Verify candidate status
    result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.id == candidate_id)
    )
    updated_candidate = result.scalar_one()
    assert updated_candidate.status == "approved"
    assert updated_candidate.decided_at is not None
    assert updated_candidate.decided_by == "admin"


async def test_approve_product_match_already_decided(client, admin_secret, db_session, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test approving an already decided product match."""
    # Create products and candidate
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    await db_session.flush()
    
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.flush()
    
    candidate = ProductMatchCandidate(
        orphan_product_id=orphan_product.id,
        canonical_product_id=canonical_product.id,
        score=0.9,
        status="approved",  # Already approved
        decided_at=datetime.now(timezone.utc),
        decided_by="admin",
    )
    db_session.add(candidate)
    await db_session.commit()
    candidate_id = candidate.id

    # Try to approve again
    response = await client.post(
        f"/api/admin/product-matches/{candidate_id}/approve",
        headers={"X-Admin-Secret": admin_secret}
    )
    assert response.status_code == 409


async def test_reject_product_match(client, admin_secret, db_session, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test rejecting a product match."""
    # Create products and candidate
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    await db_session.flush()
    
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.flush()
    
    candidate = ProductMatchCandidate(
        orphan_product_id=orphan_product.id,
        canonical_product_id=canonical_product.id,
        score=0.9,
        status="pending",
    )
    db_session.add(candidate)
    await db_session.commit()
    candidate_id = candidate.id

    # Reject
    response = await client.post(
        f"/api/admin/product-matches/{candidate_id}/reject",
        headers={"X-Admin-Secret": admin_secret}
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    db_session.expire_all()

    # Verify candidate status
    result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.id == candidate_id)
    )
    updated_candidate = result.scalar_one()
    assert updated_candidate.status == "rejected"
    assert updated_candidate.decided_at is not None
    assert updated_candidate.decided_by == "admin"


async def test_reject_product_match_already_decided(client, admin_secret, db_session, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test rejecting an already decided product match."""
    # Create products and candidate
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    await db_session.flush()
    
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.flush()
    
    candidate = ProductMatchCandidate(
        orphan_product_id=orphan_product.id,
        canonical_product_id=canonical_product.id,
        score=0.9,
        status="rejected",  # Already rejected
        decided_at=datetime.now(timezone.utc),
        decided_by="admin",
    )
    db_session.add(candidate)
    await db_session.commit()
    candidate_id = candidate.id

    # Try to reject again
    response = await client.post(
        f"/api/admin/product-matches/{candidate_id}/reject",
        headers={"X-Admin-Secret": admin_secret}
    )
    assert response.status_code == 409


async def test_approve_product_match_merge_integration(client, admin_secret, db_session, cleanup_db, platform_id):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test that approve actually merges products."""
    # Create canonical product with SaleEvent
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    await db_session.flush()
    
    # Create orphan product with SaleEvent
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.flush()
    
    # Create SaleEvents
    await db_session.execute(
        insert(SaleEvent).values([
            {
                "product_id": canonical_product.id,
                "platform_id": platform_id,
                "size_ml": 73.9,
                "sale_price": 99.0,
                "currency": "USD",
                "deleted_at": None,
            },
            {
                "product_id": orphan_product.id,
                "platform_id": platform_id,
                "size_ml": 75.0,
                "sale_price": 14000.0,  # 정가대 — 1980엔은 설계문서의 샘플가격 예시
                "currency": "JPY",
                "deleted_at": None,
            },
        ])
    )
    await db_session.commit()
    
    # Create candidate
    candidate = ProductMatchCandidate(
        orphan_product_id=orphan_product.id,
        canonical_product_id=canonical_product.id,
        score=0.9,
        status="pending",
    )
    db_session.add(candidate)
    await db_session.commit()
    candidate_id = candidate.id
    orphan_id = orphan_product.id
    canonical_id = canonical_product.id

    # Approve
    response = await client.post(
        f"/api/admin/product-matches/{candidate_id}/approve",
        headers={"X-Admin-Secret": admin_secret}
    )
    assert response.status_code == 200

    db_session.expire_all()

    # Verify merge
    # 1. Orphan should be soft-deleted
    orphan_result = await db_session.execute(
        select(Product).where(Product.id == orphan_id)
    )
    orphan_updated = orphan_result.scalar_one()
    assert orphan_updated.deleted_at is not None
    
    # 2. Canonical should have orphan's JP name
    canonical_result = await db_session.execute(
        select(Product).where(Product.id == canonical_id)
    )
    canonical_updated = canonical_result.scalar_one()
    assert canonical_updated.name_jp == "SK-II フェイシャルトリートメント エッセンス 75mL"
    
    # 3. SaleEvents should be reassigned to canonical
    sale_result = await db_session.execute(
        select(SaleEvent).where(SaleEvent.product_id == orphan_id)
    )
    assert sale_result.scalar_one_or_none() is None
    
    sale_result = await db_session.execute(
        select(SaleEvent).where(SaleEvent.product_id == canonical_id)
    )
    sales = list(sale_result.scalars().all())
    assert len(sales) == 2