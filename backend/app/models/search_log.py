import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class SearchLog(Base):
    __tablename__ = "search_logs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    lang: Mapped[str | None] = mapped_column(String(8), nullable=True)  # "auto" 기본
    results_count: Mapped[int] = mapped_column(Integer, nullable=False)
    collecting: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    __table_args__ = (Index("ix_search_logs_created_at", "created_at"),)
