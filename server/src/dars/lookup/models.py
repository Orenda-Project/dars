from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from dars.database import Base


class Grade(Base):
    __tablename__ = "grades"

    code: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)


class Subject(Base):
    __tablename__ = "subjects"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
