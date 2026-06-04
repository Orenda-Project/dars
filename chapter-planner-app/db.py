"""
Read-only staging-DB data layer for the Chapter Planning Engine (CPE).

Standalone (D-1): CPE talks to the staging Postgres directly via asyncpg — it
does NOT import anything from dars/server/. Every query here is a SELECT; the
engine never writes (no persistence of plans, D-1/D-5).

The connection pool is created lazily on first use so the app boots even when
the DB is unreachable (browse endpoints then fail with a clear 503).
"""
import os

import asyncpg
from dotenv import load_dotenv

from logging_config import get_logger

logger = get_logger(__name__)

load_dotenv("/home/hataf/taleemabad/dars/.env")
load_dotenv()  # also pick up a local .env if present (does not override)

# SQLAlchemy-style URLs carry a +asyncpg suffix; raw asyncpg wants it stripped.
_RAW_URL = (os.getenv("DARS_STAGING_DATABASE_URL") or "").replace("+asyncpg", "")

# Subject we expose for now (query is general; this just filters the list).
_SUBJECT_FILTER = "Eng"

_pool: asyncpg.Pool | None = None


class StagingDbError(RuntimeError):
    """Raised when the staging DB is unavailable or a query fails."""


async def get_pool() -> asyncpg.Pool:
    """Lazily create and return the shared read-only connection pool."""
    global _pool
    if _pool is not None:
        return _pool
    if not _RAW_URL:
        raise StagingDbError(
            "DARS_STAGING_DATABASE_URL is not set — cannot reach staging DB"
        )
    logger.info("[DB] creating asyncpg pool (lazy init)")
    try:
        _pool = await asyncpg.create_pool(
            _RAW_URL,
            min_size=1,
            max_size=4,
            command_timeout=30,
        )
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.error("[DB] pool creation failed", exc_info=True)
        raise StagingDbError(f"could not connect to staging DB: {exc}") from exc
    logger.info("[DB] pool ready")
    return _pool


async def close_pool() -> None:
    """Close the pool on shutdown."""
    global _pool
    if _pool is not None:
        logger.info("[DB] closing pool")
        await _pool.close()
        _pool = None


async def list_books() -> list[dict]:
    """Return English books: [{id, title, grade, total_chapters}]."""
    logger.info("[DB] list_books entry — subject=%s", _SUBJECT_FILTER)
    sql = """
        SELECT b.id::text AS id,
               b.title,
               g.code AS grade,
               b.total_chapters
          FROM books b
          JOIN subjects s ON s.id = b.subject_id
          JOIN grades g   ON g.id = b.grade_id
         WHERE s.code = $1
         ORDER BY b.title
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, _SUBJECT_FILTER)
    except StagingDbError:
        raise
    except Exception as exc:
        logger.error("[DB] list_books failed", exc_info=True)
        raise StagingDbError(f"list_books query failed: {exc}") from exc
    result = [dict(r) for r in rows]
    logger.info("[DB] list_books exit — books=%d", len(result))
    return result


async def list_chapters(book_id: str) -> list[dict]:
    """Return chapters for a book: [{id, chapter_number, title, topic_count}]."""
    logger.info("[DB] list_chapters entry — book_id=%s", book_id)
    sql = """
        SELECT bc.id::text AS id,
               bc.chapter_number,
               bc.title,
               (SELECT count(*) FROM topics t
                 WHERE t.book_chapter_id = bc.id) AS topic_count
          FROM book_chapters bc
         WHERE bc.book_id = $1
         ORDER BY bc.chapter_number
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(sql, book_id)
    except StagingDbError:
        raise
    except Exception as exc:
        logger.error("[DB] list_chapters failed", exc_info=True)
        raise StagingDbError(f"list_chapters query failed: {exc}") from exc
    result = [dict(r) for r in rows]
    logger.info("[DB] list_chapters exit — book_id=%s chapters=%d", book_id, len(result))
    return result


async def get_chapter_as_plan_input(
    book_chapter_id: str,
    subject: str,
    grade: int,
    period_count: int,
    curriculum: str = "ICT",
) -> dict:
    """Build a PlanRequest-shaped dict from a real chapter.

    Per-topic learning targets are the topic's sub-SLOs (topic_sub_slos →
    sub_slos), ordered by sub_slos.position. The sub_slo UUID is used as the
    SLO id so ids are unique across the chapter even when the same code appears
    on two topics (PlanRequest enforces unique SLO ids); the statement carries
    the human-readable code prefix.
    """
    logger.info(
        "[DB] get_chapter_as_plan_input entry — chapter_id=%s subject=%s grade=%s period_count=%s",
        book_chapter_id, subject, grade, period_count,
    )
    chapter_sql = "SELECT id::text, title FROM book_chapters WHERE id = $1"
    topics_sql = """
        SELECT t.id::text AS topic_id,
               t.topic_number,
               t.title AS topic_title,
               t.topic_text
          FROM topics t
         WHERE t.book_chapter_id = $1
         ORDER BY t.topic_number
    """
    slos_sql = """
        SELECT ss.id::text AS sub_slo_id,
               ss.code,
               ss.statement,
               ss.position
          FROM topic_sub_slos tss
          JOIN sub_slos ss ON ss.id = tss.sub_slo_id
         WHERE tss.topic_id = $1
         ORDER BY ss.position, ss.code
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            chapter = await conn.fetchrow(chapter_sql, book_chapter_id)
            if chapter is None:
                raise StagingDbError(f"chapter {book_chapter_id} not found")
            topic_rows = await conn.fetch(topics_sql, book_chapter_id)
            topics = []
            for tr in topic_rows:
                slo_rows = await conn.fetch(slos_sql, tr["topic_id"])
                seen: set[str] = set()
                slos = []
                for sr in slo_rows:
                    sid = sr["sub_slo_id"]
                    if sid in seen:  # de-dup within a topic
                        continue
                    seen.add(sid)
                    code = sr["code"] or ""
                    statement = sr["statement"] or ""
                    slos.append(
                        {
                            "id": sid,
                            "statement": f"[{code}] {statement}" if code else statement,
                        }
                    )
                topics.append(
                    {
                        "id": tr["topic_id"],
                        "topic_text": tr["topic_text"] or "",
                        # extra display fields (ignored by PlanRequest validation)
                        "title": tr["topic_title"],
                        "topic_number": tr["topic_number"],
                        "slos": slos,
                    }
                )
    except StagingDbError:
        raise
    except Exception as exc:
        logger.error("[DB] get_chapter_as_plan_input failed", exc_info=True)
        raise StagingDbError(f"get_chapter_as_plan_input query failed: {exc}") from exc

    plan_input = {
        "subject": subject,
        "grade": grade,
        "curriculum": curriculum,
        "period_count": period_count,
        "chapter": {
            "title": chapter["title"],
            "topics": topics,
        },
    }
    logger.info(
        "[DB] get_chapter_as_plan_input exit — chapter=%r topics=%d slos=%d",
        chapter["title"], len(topics), sum(len(t["slos"]) for t in topics),
    )
    return plan_input
