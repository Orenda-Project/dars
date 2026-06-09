import pytest
from httpx import AsyncClient, ASGITransport

from dars.main import app
from dars.v2_api import deps


@pytest.fixture(autouse=True)
def _reset_db_pool():
    """Drop the cached asyncpg pool around each test.

    pytest-asyncio gives every test a fresh (function-scoped) event loop, but
    `deps._POOL` is a module global created lazily on first use and bound to
    whatever loop created it. Reusing it from a later test's loop raises
    "Event loop is closed". Nulling the reference (without awaiting close on a
    dead loop) forces `get_db_pool()` to rebuild on the current loop. No-ops
    for the SQLite/no-DB tests that never touch the pool.
    """
    deps._POOL = None
    yield
    deps._POOL = None


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
