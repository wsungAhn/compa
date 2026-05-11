import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SaleEvent(Base):
    __tablename__ = "sale_events"
    __table_args__ = (
        Index("ix_sale_events_product_id", "product_id"),
        Index("ix_sale_events_platform_id", "platform_id"),
        Index("ix_sale_events_start_date", "start_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    platform_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("platforms.id"), nullable=False)
    event_name: Mapped[str | None] = mapped_column(String(255))
    event_type: Mapped[str | None] = mapped_column(Enum("regular", "surprise", name="event_type"))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    original_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    sale_price: Mapped[float | None] = mapped_column(Numeric(12, 2))
    discount_rate: Mapped[float | None] = mapped_column(Numeric(5, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    reason: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    needs_review: Mapped[bool | None] = mapped_column(default=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
