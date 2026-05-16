"""
F2.5 — Auto-build a draft Breakdown from a book + curriculum.

Endpoint shape (caller in router_breakdown.py):
    POST /api/v2/breakdowns/auto-build
    body: AutoBuildRequest

Algorithm (per phase doc 04-phase-2 §F2.5):
    1. Compute per-chapter teaching-day budget proportional to topic count.
    2. For each chapter, walk topics and emit:
         - 1 lesson slot per topic (we don't have a length signal yet;
           D-68 says "1-2 lessons" but for v1 keep it deterministic).
         - lp_type via lp_type_heuristics.pick_lp_type().
         - Every `fa_cadence` lesson slots, emit a formative_assessment
           slot that covers the recent `fa_cadence` topics.
         - At chapter end (after the last topic / last FA), emit
           `sa_per_chapter` summative_assessment slot(s) covering
           all topics in the chapter.
         - End each chapter with a `revision` slot.
    3. Persist as breakdown (status='draft'), breakdown_chapters, and
       breakdown_slots in one transaction.

The number of slots is intentionally not pinned to total_teaching_days —
total_teaching_days is stored on the breakdown row for the projector
(F2.8). Slot counts come from the book's topic count + cadence.
"""
import logging
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg

from dars.breakdown.lp_type_heuristics import pick_lp_type
from dars.v2_api.lp_types import is_valid_lp_type

log = logging.getLogger("breakdown.auto_build")


# ---------------------------------------------------------------------------
# Request / result dataclasses (kept independent of pydantic so the service
# can be called from a test harness without going through FastAPI).
# ---------------------------------------------------------------------------


@dataclass
class AutoBuildRequest:
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID
    total_teaching_days: int = 180
    fa_cadence: int = 5
    sa_per_chapter: int = 1
    # Optional override; if None, scope='global' is assumed.
    scope: str = "global"
    scope_ref_id: UUID | None = None


@dataclass
class AutoBuildResult:
    breakdown_id: UUID
    chapter_count: int = 0
    lesson_slot_count: int = 0
    fa_slot_count: int = 0
    sa_slot_count: int = 0
    revision_slot_count: int = 0
    total_slot_count: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def compute_chapter_day_budget(
    topic_counts_in_order: list[int],
    total_teaching_days: int,
) -> list[int]:
    """
    Split `total_teaching_days` across chapters proportional to topic count.
    Returns one budget per chapter; sum may differ by ±N due to rounding.
    Every chapter gets at least 1 day.
    """
    total_topics = sum(topic_counts_in_order)
    if total_topics <= 0:
        # No topics anywhere — give each chapter one day so something exists.
        return [1 for _ in topic_counts_in_order]
    raw = [
        (count / total_topics) * total_teaching_days for count in topic_counts_in_order
    ]
    rounded = [max(1, round(x)) for x in raw]
    # Best-effort reconciliation: nudge the largest chapter to absorb drift.
    drift = total_teaching_days - sum(rounded)
    if drift != 0 and rounded:
        idx = rounded.index(max(rounded))
        rounded[idx] = max(1, rounded[idx] + drift)
    return rounded


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


async def auto_build_breakdown(
    conn: asyncpg.Connection,
    request: AutoBuildRequest,
) -> AutoBuildResult:
    """
    Build and persist a draft breakdown. Raises ValueError on bad input.
    """
    log.info(
        "auto_build_breakdown: entry book=%s grade=%s subject=%s days=%d fa=%d sa=%d",
        request.book_id, request.grade_id, request.subject_id,
        request.total_teaching_days, request.fa_cadence, request.sa_per_chapter,
    )
    if request.fa_cadence < 1:
        raise ValueError("fa_cadence must be >= 1")
    if request.sa_per_chapter < 0:
        raise ValueError("sa_per_chapter must be >= 0")
    if request.total_teaching_days < 1:
        raise ValueError("total_teaching_days must be >= 1")

    # Load subject code for lp_type validation.
    subject_code = await conn.fetchval(
        "SELECT code FROM subjects WHERE id = $1", request.subject_id
    )
    if subject_code is None:
        raise ValueError(f"subject_id {request.subject_id} not found")

    # Verify the book matches curriculum/grade/subject.
    book = await conn.fetchrow(
        """
        SELECT id, curriculum_id, grade_id, subject_id
        FROM books
        WHERE id = $1
        """,
        request.book_id,
    )
    if book is None:
        raise ValueError(f"book_id {request.book_id} not found")
    if (
        book["curriculum_id"] != request.curriculum_id
        or book["grade_id"] != request.grade_id
        or book["subject_id"] != request.subject_id
    ):
        raise ValueError(
            "book does not match (curriculum_id, grade_id, subject_id)"
        )

    # Load chapters + topics.
    chapters = await conn.fetch(
        """
        SELECT id, chapter_number, title
        FROM book_chapters
        WHERE book_id = $1
        ORDER BY chapter_number
        """,
        request.book_id,
    )
    if not chapters:
        raise ValueError("book has no chapters")
    chapter_ids = [c["id"] for c in chapters]

    topic_rows = await conn.fetch(
        """
        SELECT t.id, t.book_chapter_id, t.topic_number, t.title, t.topic_text
        FROM topics t
        WHERE t.book_chapter_id = ANY($1::uuid[])
        ORDER BY t.book_chapter_id, t.topic_number
        """,
        chapter_ids,
    )
    topics_by_chapter: dict[UUID, list[asyncpg.Record]] = {}
    for tr in topic_rows:
        topics_by_chapter.setdefault(tr["book_chapter_id"], []).append(tr)

    # For each topic, look up the parent SLO's recommended_lp_type (via
    # topic_sub_slos → sub_slos → slos). Take the first non-null value we
    # see for the topic; ordering by sub_slo position keeps it stable.
    topic_recommended_lp: dict[UUID, str | None] = {}
    if topic_rows:
        rec_rows = await conn.fetch(
            """
            SELECT tss.topic_id, s.recommended_lp_type
            FROM topic_sub_slos tss
            JOIN sub_slos ss ON ss.id = tss.sub_slo_id
            JOIN slos s ON s.id = ss.slo_id
            WHERE tss.topic_id = ANY($1::uuid[])
              AND s.recommended_lp_type IS NOT NULL
            ORDER BY tss.topic_id, ss.position
            """,
            [t["id"] for t in topic_rows],
        )
        for r in rec_rows:
            topic_recommended_lp.setdefault(r["topic_id"], r["recommended_lp_type"])

    # Compute per-chapter day budget.
    topic_counts = [len(topics_by_chapter.get(c["id"], [])) for c in chapters]
    chapter_days = compute_chapter_day_budget(topic_counts, request.total_teaching_days)

    result = AutoBuildResult(breakdown_id=UUID(int=0))

    async with conn.transaction():
        # 1. Insert the breakdown row.
        breakdown_id = await conn.fetchval(
            """
            INSERT INTO breakdowns
              (scope, scope_ref_id, curriculum_id, grade_id, subject_id,
               book_id, total_teaching_days, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'draft')
            RETURNING id
            """,
            request.scope, request.scope_ref_id, request.curriculum_id,
            request.grade_id, request.subject_id, request.book_id,
            request.total_teaching_days,
        )
        result.breakdown_id = breakdown_id

        global_position = 0  # incremented per slot inserted

        for idx, chapter in enumerate(chapters):
            chapter_topics = topics_by_chapter.get(chapter["id"], [])
            if not chapter_topics:
                result.warnings.append(
                    f"chapter {chapter['chapter_number']} has no topics — skipping"
                )
                continue

            # 1a. Insert the breakdown_chapter row.
            bd_chapter_id = await conn.fetchval(
                """
                INSERT INTO breakdown_chapters
                  (breakdown_id, book_chapter_id, position, teaching_days)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                breakdown_id, chapter["id"], idx + 1, chapter_days[idx],
            )
            result.chapter_count += 1

            # 2. Walk topics + emit lesson + FA slots.
            chapter_position = 0
            recent_topic_ids: list[UUID] = []  # for the next FA
            chapter_topic_ids: list[UUID] = []  # for the chapter's SA(s)
            lesson_count_in_chapter = 0

            for topic in chapter_topics:
                chapter_position += 1
                global_position += 1
                lp_type = pick_lp_type(
                    subject_code=subject_code,
                    topic_title=topic["title"],
                    topic_text=topic["topic_text"],
                    recommended_lp_type=topic_recommended_lp.get(topic["id"]),
                )
                if not is_valid_lp_type(subject_code, lp_type):
                    result.warnings.append(
                        f"topic {topic['id']} got invalid lp_type {lp_type!r}; defaulting"
                    )
                    lp_type = "revision"

                await conn.execute(
                    """
                    INSERT INTO breakdown_slots
                      (breakdown_id, breakdown_chapter_id, position, chapter_position,
                       slot_type, lp_type, topic_id)
                    VALUES ($1, $2, $3, $4, 'lesson', $5, $6)
                    """,
                    breakdown_id, bd_chapter_id, global_position,
                    chapter_position, lp_type, topic["id"],
                )
                result.lesson_slot_count += 1
                recent_topic_ids.append(topic["id"])
                chapter_topic_ids.append(topic["id"])
                lesson_count_in_chapter += 1

                # FA every `fa_cadence` lessons.
                if lesson_count_in_chapter % request.fa_cadence == 0:
                    chapter_position += 1
                    global_position += 1
                    fa_slot_id = await conn.fetchval(
                        """
                        INSERT INTO breakdown_slots
                          (breakdown_id, breakdown_chapter_id, position, chapter_position,
                           slot_type, lp_type, topic_id)
                        VALUES ($1, $2, $3, $4, 'formative_assessment', NULL, NULL)
                        RETURNING id
                        """,
                        breakdown_id, bd_chapter_id, global_position, chapter_position,
                    )
                    for i, t_id in enumerate(recent_topic_ids, start=1):
                        await conn.execute(
                            """
                            INSERT INTO breakdown_slot_topics (breakdown_slot_id, topic_id, position)
                            VALUES ($1, $2, $3)
                            """,
                            fa_slot_id, t_id, i,
                        )
                    result.fa_slot_count += 1
                    recent_topic_ids = []

            # If there are recent topics not yet covered by an FA, do one final FA.
            if recent_topic_ids:
                chapter_position += 1
                global_position += 1
                fa_slot_id = await conn.fetchval(
                    """
                    INSERT INTO breakdown_slots
                      (breakdown_id, breakdown_chapter_id, position, chapter_position,
                       slot_type, lp_type, topic_id)
                    VALUES ($1, $2, $3, $4, 'formative_assessment', NULL, NULL)
                    RETURNING id
                    """,
                    breakdown_id, bd_chapter_id, global_position, chapter_position,
                )
                for i, t_id in enumerate(recent_topic_ids, start=1):
                    await conn.execute(
                        """
                        INSERT INTO breakdown_slot_topics (breakdown_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        """,
                        fa_slot_id, t_id, i,
                    )
                result.fa_slot_count += 1

            # 3. SA(s) covering all topics in the chapter.
            for _ in range(request.sa_per_chapter):
                chapter_position += 1
                global_position += 1
                sa_slot_id = await conn.fetchval(
                    """
                    INSERT INTO breakdown_slots
                      (breakdown_id, breakdown_chapter_id, position, chapter_position,
                       slot_type, lp_type, topic_id)
                    VALUES ($1, $2, $3, $4, 'summative_assessment', NULL, NULL)
                    RETURNING id
                    """,
                    breakdown_id, bd_chapter_id, global_position, chapter_position,
                )
                for i, t_id in enumerate(chapter_topic_ids, start=1):
                    await conn.execute(
                        """
                        INSERT INTO breakdown_slot_topics (breakdown_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        """,
                        sa_slot_id, t_id, i,
                    )
                result.sa_slot_count += 1

            # 4. Final revision slot.
            chapter_position += 1
            global_position += 1
            await conn.execute(
                """
                INSERT INTO breakdown_slots
                  (breakdown_id, breakdown_chapter_id, position, chapter_position,
                   slot_type, lp_type, topic_id)
                VALUES ($1, $2, $3, $4, 'revision', 'revision', NULL)
                """,
                breakdown_id, bd_chapter_id, global_position, chapter_position,
            )
            result.revision_slot_count += 1

        result.total_slot_count = (
            result.lesson_slot_count
            + result.fa_slot_count
            + result.sa_slot_count
            + result.revision_slot_count
        )

    log.info(
        "auto_build_breakdown: exit breakdown_id=%s chapters=%d lessons=%d fa=%d sa=%d rev=%d total=%d warnings=%d",
        result.breakdown_id, result.chapter_count, result.lesson_slot_count,
        result.fa_slot_count, result.sa_slot_count, result.revision_slot_count,
        result.total_slot_count, len(result.warnings),
    )
    return result
