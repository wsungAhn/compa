import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SocialPost(Base):
    __tablename__ = "social_posts"
    __table_args__ = ()

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    platform: Mapped[str] = mapped_column(
        Enum("instagram", "tiktok", "facebook", "naver_blog", "xiaohongshu", name="social_platform"),
        nullable=False,
    )
    post_url: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sale_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sale_events.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
