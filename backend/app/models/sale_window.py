"""세일 창(sale window) — 시간축에 브랜드·명목·할인폭을 붙인 관측 슬롯.

해상도를 **ISO 주차**로 잡는다. 블랙프라이데이는 11월 넷째 주로 주 단위에선 고정이지만
날짜로는 매년 움직인다 — 365칸은 대부분 비어 노이즈만 늘고, 12칸(월)은 D-day가 안
나온다. 52칸이 신호가 사는 해상도다. 정확한 날짜를 아는 관측은 `observed_on`에 함께
남겨 손실을 막는다.

모든 소스가 같은 슬롯에 쌓인다(YouTube 업로드 분포, Slickdeals, Reddit, 우리 공홈
관측). 그래서 Reddit 원문을 48시간 뒤 지워도 "그 주에 브랜드 X가 세일했다"는 집계는
우리 자산으로 남는다 — 약관 준수와 이력 축적이 여기서 양립한다.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SaleWindow(Base):
    __tablename__ = "sale_windows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── 시간축 ──────────────────────────────────────────────
    iso_year: Mapped[int] = mapped_column(Integer, nullable=False)
    iso_week: Mapped[int] = mapped_column(Integer, nullable=False)
    # 날짜를 아는 관측은 보존한다. 주차만 아는 추정(YouTube 분포)은 NULL.
    observed_on: Mapped[date | None] = mapped_column(Date)

    # ── 무엇을 ──────────────────────────────────────────────
    brand: Mapped[str] = mapped_column(String(120), nullable=False)
    # 세일의 명목. "Black Friday", "21 Days of Beauty", "Back to School"…
    event_name: Mapped[str | None] = mapped_column(String(255))
    discount_pct: Mapped[float | None] = mapped_column(Float)
    price: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(3))

    # 같은 25%라도 사이트와이드와 단일 품목은 값어치가 완전히 다르다.
    scope: Mapped[str] = mapped_column(
        Enum("sitewide", "category", "item", "unknown", name="sale_scope"),
        nullable=False,
        server_default="unknown",
    )
    # 어디서 세일했나 — 같은 브랜드라도 리테일러마다 시기가 다르다(공홈 vs Sephora vs Costco).
    retailer: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )

    # ── 출처와 신뢰 ─────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        Enum("youtube_timing", "slickdeals", "reddit", "own_observation", name="sale_window_source"),
        nullable=False,
    )
    source_url: Mapped[str | None] = mapped_column(Text)
    # 관측(실제로 그 가격을 봤다) vs 추정(하울 영상이 그 주에 몰렸다)
    is_estimate: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    # 공홈 실가격으로 교차검증됐나. 소셜 신호는 검증 전까지 가격으로 승격하지 않는다.
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    sample_size: Mapped[int | None] = mapped_column(Integer)
    corroborations: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    confidence: Mapped[float | None] = mapped_column(Float)

    # 같은 행사의 연도 간 연결 키("sephora_spring"). 이게 있어야 "작년 이 행사는 몇 주차
    # 였나"를 이름 매칭 없이 바로 찾는다 — 반복 예측의 조인 키다.
    recurrence_key: Mapped[str | None] = mapped_column(String(120))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_sale_windows_slot", "iso_year", "iso_week", "brand"),
        Index("ix_sale_windows_recurrence", "recurrence_key", "iso_year"),
        Index("ix_sale_windows_brand_week", "brand", "iso_week"),
    )
