from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DialogueGroundTruth(Base):
    __tablename__ = "dialogue_ground_truths"
    __table_args__ = (
        UniqueConstraint(
            "asset_id",
            "region_id",
            name="uq_dialogue_ground_truth_asset_region",
        ),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    asset_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    region_id: Mapped[int] = mapped_column(
        nullable=False,
    )

    raw_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    ai_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    verified_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    correction_score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    recovery_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
