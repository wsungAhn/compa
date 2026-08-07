"""Tests for cross-currency product matching task."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine
from app.ai.matching import evaluate_match
from app.models.product import Product
from app.models.sale_event import SaleEvent
from app.models.product_match_candidate import ProductMatchCandidate
from app.tasks.match_products import (
    _match_pending_products,
    _match_orphan,
    _merge_products,
    _representative_size,
    _candidate_sizes,
    _unit_price,
)


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
async def bare_product_id(db_session: AsyncSession) -> uuid.UUID:
    """SaleEvent.product_id는 FK다 — 헬퍼 단위테스트용 최소 Product 하나를 만든다."""
    product = Product(name_en=f"Bare Product {uuid.uuid4().hex[:8]}")
    db_session.add(product)
    await db_session.flush()
    return product.id


@pytest.fixture
async def cleanup_db(db_session: AsyncSession):
    """Clean up test data after each test."""
    yield
    await db_session.execute(update(ProductMatchCandidate).values(status="rejected"))
    await db_session.execute(update(Product).where(Product.name_jp.like("SK-II%")).values(deleted_at=datetime.utcnow()))
    await db_session.execute(update(Product).where(Product.name_jp.like("Different%")).values(deleted_at=datetime.utcnow()))
    await db_session.commit()


async def test_representative_size(db_session: AsyncSession, platform_id, bare_product_id):
    """Test _representative_size helper."""
    product_id = bare_product_id
    
    # 한 INSERT 문에 같이 넣으면 server_default=func.now()가 두 행에 동일한
    # created_at을 준다 — "가장 최신"이 판정 불가해진다, 명시적으로 갈라둔다.
    now = datetime.now(timezone.utc)
    await db_session.execute(
        insert(SaleEvent).values([
            {"product_id": product_id, "platform_id": platform_id, "size_ml": 50.0, "sale_price": 100.0, "currency": "USD", "deleted_at": None, "created_at": now - timedelta(minutes=1)},
            {"product_id": product_id, "platform_id": platform_id, "size_ml": 75.0, "sale_price": 150.0, "currency": "USD", "deleted_at": None, "created_at": now},
        ])
    )
    await db_session.commit()

    size = await _representative_size(db_session, product_id)
    assert size == 75.0  # Should return the most recent (largest created_at)


async def test_candidate_sizes(db_session: AsyncSession, platform_id, bare_product_id):
    """Test _candidate_sizes helper."""
    product_id = bare_product_id

    # uq_sale_events_dedup이 (product_id, platform_id, size_ml 등) 조합을 이미
    # 유니크로 강제한다 — 같은 용량이 두 번 나오는 "중복" 시나리오는 실제로는
    # 다른 플랫폼에서 같은 용량을 팔 때만 유효 데이터다.
    from app.models.platform import Platform
    platform_id_2 = (
        await db_session.execute(select(Platform.id).where(Platform.id != platform_id).limit(1))
    ).scalar_one()

    await db_session.execute(
        insert(SaleEvent).values([
            {"product_id": product_id, "platform_id": platform_id, "size_ml": 50.0, "sale_price": 100.0, "currency": "USD", "deleted_at": None},
            {"product_id": product_id, "platform_id": platform_id_2, "size_ml": 50.0, "sale_price": 120.0, "currency": "USD", "deleted_at": None},
            {"product_id": product_id, "platform_id": platform_id, "size_ml": 75.0, "sale_price": 150.0, "currency": "USD", "deleted_at": None},
        ])
    )
    await db_session.commit()
    
    sizes = await _candidate_sizes(db_session, product_id)
    assert set(sizes) == {50.0, 75.0}  # Should return distinct sizes


async def test_unit_price(db_session: AsyncSession, platform_id, bare_product_id):
    """Test _unit_price helper."""
    product_id = bare_product_id
    
    # Test with exact size match
    await db_session.execute(
        insert(SaleEvent).values([
            {"product_id": product_id, "platform_id": platform_id, "size_ml": 50.0, "sale_price": 100.0, "currency": "USD", "deleted_at": None},
            {"product_id": product_id, "platform_id": platform_id, "size_ml": 75.0, "sale_price": 150.0, "currency": "USD", "deleted_at": None},
        ])
    )
    await db_session.commit()
    
    # Exact match
    unit_price = await _unit_price(db_session, product_id, 50.0)
    assert unit_price == (100.0, "USD")
    
    # Approximate match (should find closest size)
    unit_price = await _unit_price(db_session, product_id, 52.0)
    assert unit_price == (100.0, "USD")  # Should find 50.0 as closest
    
    # No match
    unit_price = await _unit_price(db_session, product_id, 200.0)
    assert unit_price is None


async def test_match_orphan_auto_merge(db_session: AsyncSession, cleanup_db, platform_id):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test automatic merge of matching products."""
    # Create canonical product (US)
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    
    # Create orphan product (JP)
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.flush()  # .id는 default=uuid.uuid4가 flush 시점에 채운다 — 그 전엔 None

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
                # 1980엔은 설계문서의 "샘플/트라이얼" 실측 예시 가격이다 — 정가 매칭을
                # 검증하는 이 테스트에 그대로 쓰면 단가 이탈 게이트에 걸려 match 대신
                # needs_review가 나온다(리뷰 중 재현). 정가대(¥11,000선)로 교체.
                "sale_price": 14000.0,
                "currency": "JPY",
                "deleted_at": None,
            },
        ])
    )
    
    await db_session.commit()
    
    # Mock translation
    with patch("app.tasks.match_products.translate_for_matching") as mock_translate:
        mock_translate.return_value = "SK-II Facial Treatment Essence, 75ml"
        
        # Run matching
        await _match_orphan(db_session, orphan_product)
        await db_session.commit()
    
    # Verify merge
    orphan_result = await db_session.execute(
        select(Product).where(Product.id == orphan_product.id)
    )
    orphan_updated = orphan_result.scalar_one()
    assert orphan_updated.deleted_at is not None
    
    canonical_result = await db_session.execute(
        select(Product).where(Product.id == canonical_product.id)
    )
    canonical_updated = canonical_result.scalar_one()
    assert canonical_updated.name_jp == "SK-II フェイシャルトリートメント エッセンス 75mL"
    
    # Verify SaleEvent reassignment
    sale_result = await db_session.execute(
        select(SaleEvent).where(SaleEvent.product_id == orphan_product.id)
    )
    assert sale_result.scalar_one_or_none() is None
    
    sale_result = await db_session.execute(
        select(SaleEvent).where(SaleEvent.product_id == canonical_product.id)
    )
    sales = list(sale_result.scalars().all())
    assert len(sales) == 2
    
    # Verify candidate record
    candidate_result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.orphan_product_id == orphan_product.id)
    )
    candidate = candidate_result.scalar_one()
    assert candidate.status == "approved"
    assert candidate.decided_by == "auto"


async def test_match_orphan_needs_review(db_session: AsyncSession, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test needs_review path for ambiguous matches."""
    # Create canonical product
    canonical_product = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(canonical_product)
    
    # Create orphan with sample keyword
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL お試し",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    
    await db_session.commit()
    
    # Mock translation with sample keyword
    with patch("app.tasks.match_products.translate_for_matching") as mock_translate:
        mock_translate.return_value = "SK-II Facial Treatment Essence, 75ml sample"
        
        # Run matching
        await _match_orphan(db_session, orphan_product)
        await db_session.commit()
    
    # Verify no merge
    orphan_result = await db_session.execute(
        select(Product).where(Product.id == orphan_product.id)
    )
    orphan_updated = orphan_result.scalar_one()
    assert orphan_updated.deleted_at is None
    
    # Verify candidate record with pending status
    candidate_result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.orphan_product_id == orphan_product.id)
    )
    candidate = candidate_result.scalar_one()
    assert candidate.status == "pending"
    assert candidate.decided_at is None
    assert candidate.decided_by is None


async def test_match_orphan_no_candidates(db_session: AsyncSession, cleanup_db):
    """Test no candidates case."""
    # Create orphan with different brand
    orphan_product = Product(
        name_en=None,
        name_jp=f"Different Brand Essence {uuid.uuid4().hex[:8]}",
        brand=f"Different-{uuid.uuid4().hex[:8]}",
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    await db_session.commit()
    
    # Run matching
    await _match_orphan(db_session, orphan_product)
    await db_session.commit()
    
    # Verify no candidate record created
    candidate_result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.orphan_product_id == orphan_product.id)
    )
    assert candidate_result.scalar_one_or_none() is None


async def test_integrity_error_handling(db_session: AsyncSession, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test handling of IntegrityError when race condition occurs."""
    # Create orphan and pre-insert candidate
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    # canonical_product_id도 FK라 실제 존재하는 Product를 가리켜야 한다.
    some_canonical = Product(name_en=f"Unrelated Canonical {uuid.uuid4().hex[:8]}")
    db_session.add(some_canonical)
    await db_session.flush()

    # Pre-insert candidate to simulate race condition
    existing_candidate = ProductMatchCandidate(
        orphan_product_id=orphan_product.id,
        canonical_product_id=some_canonical.id,
        score=0.9,
        status="approved",
    )
    db_session.add(existing_candidate)
    await db_session.commit()
    
    # Mock translation
    with patch("app.tasks.match_products.translate_for_matching") as mock_translate:
        mock_translate.return_value = "SK-II Facial Treatment Essence, 75ml"
        
        # Run matching - should not raise exception
        await _match_orphan(db_session, orphan_product)
        await db_session.commit()
    
    # Verify no duplicate candidate
    candidate_result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.orphan_product_id == orphan_product.id)
    )
    candidates = list(candidate_result.scalars().all())
    assert len(candidates) == 1  # Should still be only the original


async def test_tie_break_logic(db_session: AsyncSession, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Test tie-break logic where match should win over needs_review."""
    # Create two canonical products
    canonical1 = Product(
        name_en="Facial Treatment Essence",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    canonical2 = Product(
        name_en="Facial Treatment Essence Trial",
        brand=brand,
        name_jp=None,
        name_kr=None,
        name_cn=None,
    )
    db_session.add_all([canonical1, canonical2])
    
    # Create orphan
    orphan_product = Product(
        name_en=None,
        name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
        brand=brand,
        name_kr=None,
        name_cn=None,
    )
    db_session.add(orphan_product)
    
    await db_session.commit()
    
    # canonical1(match)이 canonical2(needs_review)보다 containment_score가 낮아도
    # 이겨야 한다(적대감사 R1 tie-break) — 후보 순회 순서는 보장되지 않으므로 이름으로
    # 판정하는 side_effect를 써서 순서 무관하게 만든다.
    def fake_evaluate_match(canonical_name, listing_name, **kwargs):
        return "needs_review" if canonical_name == canonical2.name_en else "match"

    def fake_containment_score(canonical_name, listing_name):
        return 0.95 if canonical_name == canonical2.name_en else 0.9

    with patch("app.tasks.match_products.translate_for_matching") as mock_translate:
        mock_translate.return_value = "SK-II Facial Treatment Essence, 75ml"

        with patch("app.tasks.match_products.evaluate_match", side_effect=fake_evaluate_match), \
             patch("app.tasks.match_products.containment_score", side_effect=fake_containment_score):
            await _match_orphan(db_session, orphan_product)
            await db_session.commit()
    
    # Verify that match verdict was chosen despite lower score
    candidate_result = await db_session.execute(
        select(ProductMatchCandidate).where(ProductMatchCandidate.orphan_product_id == orphan_product.id)
    )
    candidate = candidate_result.scalar_one()
    assert candidate.status == "approved"
    assert candidate.canonical_product_id == canonical1.id


async def test_match_pending_products_integration(db_session: AsyncSession, cleanup_db):
    brand = f"SK-II-{uuid.uuid4().hex[:8]}"
    """Integration test for _match_pending_products with multiple orphans."""
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
    canonical_id = canonical_product.id

    # Create multiple orphans
    different_brand = f"Different-{uuid.uuid4().hex[:8]}"
    orphans = [
        Product(
            name_en=None,
            name_jp="SK-II フェイシャルトリートメント エッセンス 75mL",
            brand=brand,
            name_kr=None,
            name_cn=None,
        ),
        Product(
            name_en=None,
            name_jp=f"Different Brand Essence {uuid.uuid4().hex[:8]}",
            brand=different_brand,
            name_kr=None,
            name_cn=None,
        ),
    ]
    for orphan in orphans:
        db_session.add(orphan)

    await db_session.commit()

    # Mock translation
    with patch("app.tasks.match_products.translate_for_matching") as mock_translate:
        mock_translate.return_value = "SK-II Facial Treatment Essence, 75ml"

        # Run batch matching
        count = await _match_pending_products(limit=10)
        await db_session.commit()

    # _match_pending_products는 카탈로그 전체를 스캔한다(이 테스트가 만든 orphan에
    # 스코프가 갇혀있지 않다) — 정확한 전역 카운트를 단언하지 않는다, 이 테스트가
    # 만든 두 orphan이 최소한 처리됐는지만 확인한다.
    assert count >= 2

    db_session.expire_all()

    # Verify canonical has merged data
    canonical_result = await db_session.execute(
        select(Product).where(Product.id == canonical_id)
    )
    canonical_updated = canonical_result.scalar_one()
    assert canonical_updated.name_jp is not None

    # Verify different brand orphan is unchanged
    different_result = await db_session.execute(
        select(Product).where(Product.brand == different_brand)
    )
    different_updated = different_result.scalar_one()
    assert different_updated.deleted_at is None