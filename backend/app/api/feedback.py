import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.limiter import limiter
from app.models.feedback import Feedback

router = APIRouter(tags=["feedback"])


def _is_authorized_feedback_secret(secret: str) -> bool:
    """admin_secret이 설정돼 있고 정확히 일치할 때만 True (미설정 시 항상 비활성)."""
    configured = settings.admin_secret
    return configured is not None and secret == configured


class FeedbackIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    contact: str | None = Field(None, max_length=255)
    page: str | None = Field(None, max_length=100)


class FeedbackOut(BaseModel):
    id: uuid.UUID
    message: str
    contact: str | None
    page: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/api/feedback")
@limiter.limit("5/minute")
async def post_feedback(request: Request, body: FeedbackIn) -> dict[str, bool]:
    async with AsyncSessionLocal() as db:
        feedback = Feedback(
            message=body.message,
            contact=body.contact,
            page=body.page,
            created_at=datetime.now(timezone.utc),
        )
        db.add(feedback)
        await db.commit()
    return {"ok": True}


@router.get("/api/admin/feedback", response_model=list[FeedbackOut])
async def get_admin_feedback(secret: str) -> list[FeedbackOut]:
    if not _is_authorized_feedback_secret(secret):
        raise HTTPException(status_code=404, detail="Not found")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Feedback).order_by(Feedback.created_at.desc()).limit(100)
        )
        rows = list(result.scalars().all())
    return [FeedbackOut.model_validate(r) for r in rows]
