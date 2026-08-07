import logging
import pathlib
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api.comparison import router as comparison_router
from app.api.feedback import router as feedback_router
from app.api.jobs import router as jobs_router
from app.api.products import router as products_router
from app.api.admin import router as admin_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.limiter import limiter
from app.core.seed import seed_platforms
from app.models.product import Product

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    async with AsyncSessionLocal() as db:
        await seed_platforms(db)
        result = await db.execute(select(Product).limit(1))
        if result.scalar_one_or_none() is None:
            try:
                from app.tasks.seed import seed_catalog_task

                seed_catalog_task.delay()  # type: ignore[attr-defined]
                logger.info("Catalog seed dispatched to Celery background task")
            except Exception:
                logger.warning("Celery unavailable — skipping catalog seed at startup")
    yield


app = FastAPI(title="COMPA API", version="0.1.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products_router)
app.include_router(comparison_router)
app.include_router(jobs_router)
app.include_router(feedback_router)
app.include_router(admin_router)


@app.get("/health")
async def health_check() -> dict[str, object]:
    from app.scrapers.collector import get_enabled_scrapers
    from app.scrapers.firecrawl_client import get_firecrawl_status
    return {
        "status": "ok",
        "version": "0.1.0",
        "enabled_scrapers": list(get_enabled_scrapers().keys()),
        "firecrawl": await get_firecrawl_status(),
    }


# 빌드된 프론트엔드를 같은 오리진에서 서빙한다. 별도 정적 서버 프로세스가 없어지고
# /api와 same-origin이라 CORS 문제도 사라진다 (dist가 없으면 API 전용으로 동작).
_DIST = pathlib.Path(__file__).resolve().parents[2] / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
