from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReaderRouterValidationReview(Base):
    __tablename__ = "reader_router_validation_reviews"

    sample_id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    asset_id: Mapped[str] = mapped_column(String, ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    page_order: Mapped[int] = mapped_column(Integer)
    logical_region_id: Mapped[str] = mapped_column(String)
    bbox: Mapped[list] = mapped_column(JSON)
    source_image_hash: Mapped[str] = mapped_column(String)
    representation_hash: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String, default="PENDING")
    human_transcription: Mapped[str | None] = mapped_column(Text, nullable=True)
    provenance: Mapped[str] = mapped_column(String, default="human")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
