from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReadingOrderBenchmarkReview(Base):
    __tablename__ = "reading_order_benchmark_reviews"
    __table_args__ = (UniqueConstraint("asset_id", name="uq_reading_order_benchmark_asset"),)

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    page_order: Mapped[int] = mapped_column(Integer)
    source_image_hash: Mapped[str] = mapped_column(String)
    reader_revision: Mapped[str] = mapped_column(String)
    reading_policy: Mapped[str] = mapped_column(String, default="MANGA_RTL")
    predicted_groups: Mapped[list] = mapped_column(JSON)
    predicted_sequence: Mapped[list] = mapped_column(JSON)
    predicted_ambiguity: Mapped[dict] = mapped_column(JSON)
    human_groups: Mapped[list | None] = mapped_column(JSON, nullable=True)
    human_sequence: Mapped[list | None] = mapped_column(JSON, nullable=True)
    human_dispositions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state: Mapped[str] = mapped_column(String, default="PENDING")
    source_compatible: Mapped[bool] = mapped_column(Boolean, default=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
