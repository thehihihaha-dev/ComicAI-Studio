from datetime import datetime, timezone
import uuid

from sqlalchemy import String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DialogueGroundTruth(Base):
    __tablename__ = "dialogue_ground_truths"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    asset_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("assets.id"),
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