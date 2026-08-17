from datetime import datetime, timezone
import uuid

from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ProjectShortScript(Base):
    __tablename__ = "project_short_scripts"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_project_short_scripts_project_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    result: Mapped[dict] = mapped_column(JSON, nullable=False)
    segment_edits: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    style: Mapped[str] = mapped_column(String, nullable=False)
    source_story_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    source_story_approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_fingerprint: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
