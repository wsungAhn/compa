"""제품 카탈로그 시딩 — Naver Shopping API로 인기 뷰티 브랜드 제품명 수집."""
import asyncio
import logging

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.sale_event import SaleEvent

logger = logging.getLogger(__name__)

# 시딩할 인기 뷰티 브랜드 (한국 + 글로벌)
SEED_BRANDS: list[str] = [
    # ── 한국 브랜드 ────────────────────────────────────
    "설화수", "헤라", "이니스프리", "라네즈", "마몽드",
    "에뛰드하우스", "미샤", "네이처리퍼블릭", "더페이스샵",
    "닥터자르트", "코스알엑스", "조선미녀", "토리든", "클리오",
    "롬앤", "3CE", "토니모리", "제이준", "바이오더마",
    "탐버린즈", "젝시믹스",

    # ── 럭셔리 / 하이엔드 (보그 코리아 기준) ──────────
    # 초럭셔리 스킨케어
    "La Mer", "La Prairie", "Clé de Peau Beauté", "Valmont",
    "Augustinus Bader", "Swiss Perfection",
    # 럭셔리 스킨케어
    "Sisley Paris", "Chantecaille", "Tatcha", "Tata Harper",
    "Pola BA", "Shiseido Future Solution",
    # 럭셔리 메이크업
    "Chanel Beauty", "Dior Beauty", "Tom Ford Beauty",
    "YSL Beauty", "Charlotte Tilbury", "NARS", "Hourglass",
    "Pat McGrath Labs", "Hermès Beauty",
    # 니치 퍼퓸 / 프래그런스
    "Jo Malone", "Diptyque", "Byredo",
    "Maison Francis Kurkdjian", "Frederic Malle", "Kilian Paris",
    "Guerlain", "Aesop",
    # 프리미엄
    "Lancome", "Estee Lauder", "SK-II", "Shiseido",
    "Clinique", "Fresh", "Kiehl's", "Clarins", "Laura Mercier",

    # ── 가성비 브랜드 ──────────────────────────────────
    # 한국 가성비
    "COSRX", "Some By Mi", "Anua", "Purito", "IUNIK",
    "Beauty of Joseon", "Skin1004", "Mixsoon", "Round Lab",
    "Medicube", "Isntree", "Dear Klairs", "Papa Recipe",
    "Benton", "Haruharu Wonder",
    # 글로벌 가성비
    "The Ordinary", "CeraVe", "Neutrogena", "Cetaphil",
    "Drunk Elephant", "Paula's Choice", "The Inkey List",
    "Glow Recipe", "Good Molecules", "Acwell",
    "e.l.f. Cosmetics", "NYX Professional Makeup",
    "Wet n Wild", "Milani", "Flower Beauty",

    # ── 베타 타깃 — 브랜드+대표제품 검색어 (첫 검색 적중률 향상) ──
    "설화수 윤조에센스", "설화수 퍼펙팅쿠션", "설화수 자정크림",
    "헤라 블랙쿠션", "헤라 센슈얼 누드 글로스",
    "이니스프리 그린티씨드세럼", "이니스프리 블랙티 유스 앰플",
    "라네즈 워터슬리핑마스크", "라네즈 네오쿠션", "라네즈 립슬리핑마스크",
    "닥터자르트 시카페어쿠션", "닥터자르트 세라마이딘크림",
    "코스알엑스 달팽이크림", "코스알엑스 BHA블랙헤드파워리퀴드",
    "조선미녀 쌀선크림", "조선미녀 맑은쌀선크림",
    "토리든 다이브인세럼", "토리든 다이브인마스크",
    "롬앤 쥬시래스팅틴트", "클리오 킬커버쿠션",
    "SK-II 페이셜트리트먼트에센스",
    "에스티로더 갈색병", "랑콤 제니피크세럼",
    "The Ordinary 나이아신아마이드", "CeraVe 모이스처라이징크림",
    "Tatcha The Water Cream", "Drunk Elephant C-Firma",
    "Paula's Choice BHA",
]


async def seed_catalog(db: AsyncSession, brands: list[str] | None = None) -> int:
    """인기 브랜드 Naver 검색 결과를 products 테이블에 시딩.

    Returns:
        삽입된 신규 제품 수
    """
    from app.core.config import settings
    from app.scrapers.collector import get_enabled_scrapers

    if not settings.naver_client_id or not settings.naver_client_secret:
        logger.warning("Naver API key not configured, skipping catalog seed")
        return 0

    # 네이버쇼핑이 enabled_scrapers에 없으면 시딩 스킵
    if "네이버쇼핑" not in get_enabled_scrapers():
        logger.warning("네이버쇼핑 scraper not enabled, skipping catalog seed")
        return 0

    from app.scrapers.kr.naver_shop import NaverShopScraper

    target_brands = brands or SEED_BRANDS
    scraper = NaverShopScraper()
    seeded = 0

    for brand in target_brands:
        try:
            items = await scraper._search_products(brand, display=20)
            for item in items:
                clean = item.title.replace("<b>", "").replace("</b>", "")
                if not clean:
                    continue
                # 동일 name_kr 제품이 이미 있으면 스킵
                # (사용자가 수집한 이벤트가 있는 제품은 절대 덮어쓰지 않음)
                existing = await db.execute(
                    select(Product).where(
                        Product.name_kr == clean,
                        Product.deleted_at.is_(None),
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                product = Product(
                    name_kr=clean,
                    name_en=clean,
                    brand=item.brand or brand,
                )
                db.add(product)
                seeded += 1
            await db.commit()
            logger.info("Seeded brand '%s': %d items", brand, len(items))
        except Exception as exc:
            logger.warning("Failed to seed brand '%s': %s", brand, exc)
            await db.rollback()
        await asyncio.sleep(0.6)  # Naver API rate limit

    logger.info("Catalog seed complete: %d new products", seeded)
    return seeded


async def seed_catalog_if_empty(db: AsyncSession) -> None:
    """products 테이블이 비어있을 때만 카탈로그 시딩 실행.

    이미 사용자가 수집한 제품(이벤트 보유)이 있으면 완전히 스킵.
    카탈로그만 있는 빈 상태(제품 없음)에서만 시딩.
    """
    result = await db.execute(select(Product).limit(1))
    if result.scalar_one_or_none() is None:
        logger.info("Products table is empty — starting catalog seed...")
        await seed_catalog(db)
