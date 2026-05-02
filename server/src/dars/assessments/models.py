import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid

from dars.database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lesson_plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lesson_plans.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="PENDING")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answers_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
