import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select

from app.api.comparison import router as comparison_router
from app.api.jobs import router as jobs_router
from app.api.products import router as products_router
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


@app.get("/health")
async def health_check() -> dict[str, object]:
    from app.scrapers.collector import get_enabled_scrapers
    return {
        "status": "ok",
        "version": "0.1.0",
        "enabled_scrapers": list(get_enabled_scrapers().keys()),
    }
