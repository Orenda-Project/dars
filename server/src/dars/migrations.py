"""
Lightweight migration runner.

Scans server/src/dars/migrations/*.sql in filename order, tracks applied
migrations in a `schema_migrations` table, and runs any pending ones on
startup. Works against any PostgreSQL URL (Railway, local, etc).

Uses asyncpg directly so it works before SQLAlchemy models are set up.
"""
import logging
import os
from pathlib import Path

import asyncpg

log = logging.getLogger("migrations")

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _asyncpg_url(database_url: str) -> str:
    """Convert SQLAlchemy URL scheme to plain asyncpg scheme."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://")


async def run_migrations(database_url: str) -> None:
    url = _asyncpg_url(database_url)
    conn = await asyncpg.connect(url)

    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        applied = {
            row["filename"]
            for row in await conn.fetch("SELECT filename FROM schema_migrations")
        }

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        pending = [f for f in migration_files if f.name not in applied]

        if not pending:
            log.info("Migrations: all up to date (%d applied)", len(applied))
            return

        log.info("Migrations: %d pending, %d already applied", len(pending), len(applied))

        for path in pending:
            sql = path.read_text(encoding="utf-8")
            log.info("Applying migration: %s", path.name)
            await conn.execute(sql)
            # Recreate schema_migrations in case the migration just dropped it (reset migration)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    filename TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            await conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
            )
            log.info("Applied: %s", path.name)

        log.info("Migrations: done")

    finally:
        await conn.close()
