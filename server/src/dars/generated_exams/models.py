from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from dars.database import Base


class GeneratedExam(Base):
    __tablename__ = "generated_exams"

    client_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    # curriculum, subject, grade are denormalized display fields — no FK constraint
    curriculum: Mapped[str] = mapped_column(String(50), nullable=False)
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    page_ranges: Mapped[str] = mapped_column(Text, nullable=False)
    generation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="exam")
    eg_job_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
