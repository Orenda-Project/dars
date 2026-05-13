from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from dars.database import Base


class CurriculumData(Base):
    __tablename__ = "curriculums"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
