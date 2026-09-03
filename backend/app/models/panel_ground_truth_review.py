from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PanelGroundTruthReview(Base):
    __tablename__ = "panel_ground_truth_reviews"

    review_id: Mapped[str] = mapped_column(String, primary_key=True)
    benchmark_asset_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    page_order: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    selection_role: Mapped[str] = mapped_column(String)
    source_image_hash: Mapped[str] = mapped_column(String)
    source_path: Mapped[str] = mapped_column(String)
    image_width: Mapped[int] = mapped_column(Integer)
    image_height: Mapped[int] = mapped_column(Integer)
    human_panels: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String, default="PENDING")
    revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
