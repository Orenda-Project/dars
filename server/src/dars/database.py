import uuid as _uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import Uuid

from dars.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# BigInteger that falls back to Integer for SQLite (required for autoincrement to work)
_BIGINT = BigInteger().with_variant(Integer, "sqlite")


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(_BIGINT, primary_key=True, autoincrement=True)
    uuid: Mapped[_uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), unique=True, default=_uuid.uuid4, nullable=False
    )
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
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
