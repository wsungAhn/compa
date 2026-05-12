from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import Platform

PLATFORMS = [
    {"name": "올리브영", "country": "KR", "url": "https://www.oliveyoung.co.kr", "scrape_method": "scraping"},
    {"name": "네이버쇼핑", "country": "KR", "url": "https://shopping.naver.com", "scrape_method": "official_api"},
    {"name": "쿠팡", "country": "KR", "url": "https://www.coupang.com", "scrape_method": "scraping"},
    {"name": "Sephora", "country": "US", "url": "https://www.sephora.com", "scrape_method": "scraping"},
    {"name": "Ulta", "country": "US", "url": "https://www.ulta.com", "scrape_method": "scraping"},
    {"name": "Amazon US", "country": "US", "url": "https://www.amazon.com", "scrape_method": "official_api"},
    {"name": "@cosme", "country": "JP", "url": "https://www.cosme.net", "scrape_method": "scraping"},
    {"name": "Rakuten", "country": "JP", "url": "https://www.rakuten.co.jp", "scrape_method": "official_api"},
    {"name": "Tmall", "country": "CN", "url": "https://www.tmall.com", "scrape_method": "unofficial_api"},
    {"name": "小红书", "country": "CN", "url": "https://www.xiaohongshu.com", "scrape_method": "scraping"},
]


async def seed_platforms(db: AsyncSession) -> None:
    for p in PLATFORMS:
        exists = await db.execute(select(Platform).where(Platform.name == p["name"]))
        if not exists.scalar_one_or_none():
            db.add(Platform(**p))  # type: ignore[arg-type]
    await db.commit()
