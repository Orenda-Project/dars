"""
Dars v2 seed runner.

Usage:
    make seed
    # or, directly:
    cd server && uv run python -m dars.seeds.v2_seed

Idempotent: re-running this script never duplicates rows.
IDs are deterministic UUID v5 derived from a stable namespace + a content
key, so any test or downstream code can hard-reference seed rows by
recomputing the same UUID.

Build incrementally — each feature in Phase 1 adds a step here:
- F1.2: seed_lookups()                  — grades, subjects, curriculums
- F1.3: seed_dars_english_g1_slos()     — SLOs + sub-SLOs
- F1.4: seed_dars_english_g1_book()     — book, chapters, topics, mappings
- F1.5: seed_demo_tenancy()             — org, school, AY, class, teacher, CST, timetable

Each step prints a one-line summary of what it inserted.
"""
import asyncio
import logging
import os
import sys

import asyncpg

from dars.seeds.lookups import seed_lookups
from dars.seeds.slos_dars_english_g1 import seed_dars_english_g1_slos

log = logging.getLogger("v2_seed")


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _run_all_steps(conn: asyncpg.Connection) -> None:
    """Run every Phase 1 seed step in order. Each step is idempotent."""
    # F1.2 — lookups
    await seed_lookups(conn)
    # F1.3 — SLOs + sub-SLOs for Dars Curriculum × Grade 1 × English
    await seed_dars_english_g1_slos(conn)
    # F1.4 — book + chapters + topics (next feature)
    # F1.5 — demo tenancy (next feature)


async def main() -> None:
    """Standalone entrypoint: `make seed`."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        log.error("DATABASE_URL not set")
        sys.exit(1)

    url = _asyncpg_url(database_url)
    log.info("v2_seed: connecting to %s", url.split("@")[-1])  # hide creds

    conn = await asyncpg.connect(url)
    try:
        await _run_all_steps(conn)
        log.info("v2_seed: done")
    finally:
        await conn.close()


async def run_seed_on_startup(database_url: str) -> None:
    """
    Server-boot entrypoint, called from main.py lifespan after migrations.

    Runs unconditionally on every boot. Every seed step is idempotent
    (INSERT ON CONFLICT DO NOTHING with deterministic UUID v5 IDs), so
    subsequent boots are a near-instant no-op — just three sub-queries
    that all collide on unique constraints and skip.

    Never raises: if the seed fails for any reason, we log and continue so
    the server still boots. The seed can also be re-run manually via
    `make seed`.
    """
    log.info("v2_seed: starting on-startup run")
    try:
        url = _asyncpg_url(database_url)
        conn = await asyncpg.connect(url)
        try:
            await _run_all_steps(conn)
            log.info("v2_seed: on-startup run done")
        finally:
            await conn.close()
    except Exception:
        log.exception("v2_seed: on-startup run FAILED — server will continue, run `make seed` manually")


if __name__ == "__main__":
    asyncio.run(main())
