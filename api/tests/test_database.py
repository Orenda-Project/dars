from sqlalchemy.ext.asyncio import AsyncSession
from dars.database import get_db, engine, Base


async def test_db_session_yields_async_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    gen = get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)
    await gen.aclose()
