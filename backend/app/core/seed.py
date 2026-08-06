from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import Platform
from app.scrapers.brands.shopify import BRANDS

PLATFORMS = [
    {"name": "올리브영", "country": "KR", "url": "https://www.oliveyoung.co.kr", "scrape_method": "scraping"},
    {"name": "쿠팡", "country": "KR", "url": "https://www.coupang.com", "scrape_method": "scraping"},
    {"name": "Sephora", "country": "US", "url": "https://www.sephora.com", "scrape_method": "scraping"},
    {"name": "Ulta", "country": "US", "url": "https://www.ulta.com", "scrape_method": "scraping"},
    {"name": "Amazon US", "country": "US", "url": "https://www.amazon.com", "scrape_method": "official_api"},
    {"name": "@cosme", "country": "JP", "url": "https://www.cosme.net", "scrape_method": "scraping"},
    {"name": "Rakuten", "country": "JP", "url": "https://www.rakuten.co.jp", "scrape_method": "official_api"},
    {"name": "Tmall", "country": "CN", "url": "https://www.tmall.com", "scrape_method": "unofficial_api"},
    {"name": "小红书", "country": "CN", "url": "https://www.xiaohongshu.com", "scrape_method": "official_api"},
    {"name": "Instagram", "country": "US", "url": "https://www.instagram.com", "scrape_method": "official_api"},
    {"name": "TikTok", "country": "US", "url": "https://www.tiktok.com", "scrape_method": "official_api"},
    {"name": "Facebook", "country": "US", "url": "https://www.facebook.com", "scrape_method": "official_api"},
    {"name": "네이버블로그", "country": "KR", "url": "https://blog.naver.com", "scrape_method": "official_api"},
    {"name": "Shiseido Official", "country": "US", "url": "https://www.shiseido.com", "scrape_method": "scraping"},
    {"name": "La Mer Official KR", "country": "KR", "url": "https://www.lamerkorea.com", "scrape_method": "scraping"},
    {"name": "Chantecaille Official KR", "country": "KR", "url": "https://chantecaille.kr", "scrape_method": "scraping"},
    {"name": "아모레몰", "country": "KR", "url": "https://www.amoremall.com", "scrape_method": "scraping"},
]

# 브랜드 공홈은 스크래퍼 레지스트리에서 파생한다 — 브랜드를 늘릴 때 시드를 같이
# 고치는 걸 잊으면 _get_platform이 None을 반환해 수집이 조용히 스킵된다.
PLATFORMS += [
    {"name": name, "country": "US", "url": f"https://{domain}", "scrape_method": "official_api"}
    for name, domain, _brand in BRANDS
]


async def seed_platforms(db: AsyncSession) -> None:
    for p in PLATFORMS:
        exists = await db.execute(select(Platform).where(Platform.name == p["name"]))
        if not exists.scalar_one_or_none():
            db.add(Platform(**p))
    await db.commit()
