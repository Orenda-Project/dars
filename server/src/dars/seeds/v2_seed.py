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

from dars.seeds.book_dars_english_g1 import seed_dars_english_g1_book
from dars.seeds.breakdown_demo import seed_demo_breakdown
from dars.seeds.lookups import seed_lookups
from dars.seeds.slos_dars_english_g1 import seed_dars_english_g1_slos
from dars.seeds.tenancy_demo import seed_demo_tenancy

log = logging.getLogger("v2_seed")


def _asyncpg_url(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def _run_all_steps(conn: asyncpg.Connection) -> None:
    """
    Run the data-bank seed steps in order. Each step is idempotent.

    Only the foundational "data bank" is auto-seeded (lookups, SLOs, book +
    chapters + topics). The demo *operational* data (tenancy + breakdown) is
    NO LONGER auto-seeded — orgs/schools/teachers/classes/CSTs/breakdowns are
    created through the product's own tools instead. See
    docs/features/.../ (operational-data is user-created, 2026-06-02).
    """
    # F1.2 — lookups
    await seed_lookups(conn)
    # F1.3 — SLOs + sub-SLOs for Dars Curriculum × Grade 1 × English
    await seed_dars_english_g1_slos(conn)
    # F1.4 — Book + chapters + topics + SLO/sub-SLO mappings
    await seed_dars_english_g1_book(conn)
    # NOTE: seed_demo_tenancy + seed_demo_breakdown intentionally NOT run on
    # startup anymore (2026-06-02). They are run only via `make seed --with-demo`
    # (see _run_demo_steps); staging/prod build operational data via the dashboard.


async def _run_demo_steps(conn: asyncpg.Connection) -> None:
    """Demo *operational* data — only for local dev / explicit `make seed --with-demo`."""
    # F1.5 — Demo tenancy: org, school, AY, class, teacher, CST, timetable
    await seed_demo_tenancy(conn)
    # F2.14 — Demo breakdown: published global → org → class with realized slots
    await seed_demo_breakdown(conn)


async def main() -> None:
    """Standalone entrypoint: `make seed` (add --with-demo for operational demo data)."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        log.error("DATABASE_URL not set")
        sys.exit(1)

    with_demo = "--with-demo" in sys.argv
    url = _asyncpg_url(database_url)
    log.info("v2_seed: connecting to %s (with_demo=%s)", url.split("@")[-1], with_demo)  # hide creds

    conn = await asyncpg.connect(url)
    try:
        await _run_all_steps(conn)
        if with_demo:
            await _run_demo_steps(conn)
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
