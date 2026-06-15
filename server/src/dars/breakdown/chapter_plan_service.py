"""
Chapter Plan — break-it-down service.

Computes a chapter's slot_count from the teacher's real timetable (D-9), builds
a PlanRequest from the live DB (F2.1), drives the intelligent chapter planner
(`make_chapter_plan`, Phase 1) and persists each Plan Unit into the class slot
tables (D-9), then no fallback on planner failure (D-5).

Persistence is now slot_type-aware (exam-periods-and-formative-assessments
D-9, F-2.4): a 'lesson' unit becomes a `class_lesson_slot` (+ its
`class_lesson_slot_topics` grouping) exactly as before; a 'formative_assessment'
unit becomes a `class_assessment_slot` (`assessment_type='formative'`) plus its
`class_assessment_slot_topics` grouping. Both kinds share the one global
`position` sequence per CST so the projector can merge them by position. This
SUPERSEDES the prior chapter-planner-in-dars D-1 ("no assessment slots are
created") for the FA path — that decision still holds for summative (none are
created here; D-12/D-16).
"""
import logging
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

import asyncpg

from dars.breakdown.chapter_calendar import (
    get_breakdown_exam_dates,
    get_breakdown_holiday_dates,
)
from dars.breakdown.holidays import get_effective_holidays
from dars.breakdown.planner import make_chapter_plan
from dars.breakdown.planner_llm import AgentSdkPlannerLLM, PlannerLLM
from dars.breakdown.planner_models import PlanRequest
from dars.breakdown.projector import compute_teaching_days

log = logging.getLogger("breakdown.chapter_plan")

# dynamic-chapter-planner D-14: org-wide completion target when the column is
# absent (e.g. an org row predating the migration on a stale read). Matches the
# migration's literal DEFAULT 0.80.
DEFAULT_COMPLETION_TARGET = 0.80


# ---------------------------------------------------------------------------
# Buffer-budgeted planning — pure math (dynamic-chapter-planner F-2.2, D-14/D-16)
# ---------------------------------------------------------------------------


def compute_buffer_budget(
    teaching_days: int, completion_target: float
) -> tuple[int, int]:
    """
    Split a chapter's teaching days into a MANDATORY budget + a FLEX buffer
    (D-3/D-4/D-14/D-16). 1 slot = 1 teaching day, so the two sum to
    `teaching_days`:

        mandatory_budget = round(teaching_days * completion_target)
        flex_count       = teaching_days - mandatory_budget

    Guarantees (D-16):
      - mandatory_budget is clamped to >= 1 (a chapter always teaches at least
        one mandatory unit) and <= teaching_days (can't exceed the day count);
      - a short chapter rounds flex to zero and leans on the shared end-of-term
        pool (D-4): e.g. 1 day → (1, 0); 2 days @0.8 → round(1.6)=2 → (2, 0);
        3 days @0.8 → round(2.4)=2 → (2, 1).

    `completion_target` is the org's `default_completion_target` (D-14); the
    leftover after per-chapter rounding is the natural slack that forms the thin
    shared remainder pool (D-4) — it is not materialised here (break-it-down is
    per-chapter), it is the tail slack the projector absorbs.

    Pure function — no DB, unit-tested directly (F-2.4).
    """
    if teaching_days < 1:
        return 0, 0
    mandatory = round(teaching_days * completion_target)
    mandatory = max(1, min(mandatory, teaching_days))
    flex = teaching_days - mandatory
    return mandatory, flex


# ---------------------------------------------------------------------------
# Teacher Chapter Plan — DB-facing (Phase 3, D-9/D-14/D-16)
# ---------------------------------------------------------------------------


@dataclass
class CstSyllabusContext:
    """Resolved (curriculum, grade, subject, book) for a CST + its syllabus."""
    cst_id: UUID
    curriculum_id: UUID
    grade_id: UUID
    subject_id: UUID
    book_id: UUID | None
    subject_code: str
    syllabus_breakdown_id: UUID | None  # None if no published global syllabus


async def resolve_cst_syllabus_context(
    conn: asyncpg.Connection, cst_id: UUID
) -> CstSyllabusContext:
    """
    Resolve a CST to its (curriculum via org, grade via class, subject direct)
    and the published global Syllabus Breakdown for that triple.
    Raises ValueError if the CST isn't found.
    """
    row = await conn.fetchrow(
        """
        SELECT cst.subject_id, cst.book_id,
               sc.grade_id,
               o.curriculum_id,
               s.code AS subject_code
        FROM class_subject_teachers cst
        JOIN school_classes sc ON sc.id = cst.school_class_id
        JOIN organizations o   ON o.id = cst.org_id
        JOIN subjects s        ON s.id = cst.subject_id
        WHERE cst.id = $1
        """,
        cst_id,
    )
    if row is None:
        raise ValueError(f"cst {cst_id} not found")

    syllabus_id = await conn.fetchval(
        """
        SELECT id FROM syllabus_breakdowns
        WHERE status = 'published'
          AND curriculum_id = $1 AND grade_id = $2 AND subject_id = $3
        ORDER BY created_at DESC
        LIMIT 1
        """,
        row["curriculum_id"], row["grade_id"], row["subject_id"],
    )
    return CstSyllabusContext(
        cst_id=cst_id,
        curriculum_id=row["curriculum_id"],
        grade_id=row["grade_id"],
        subject_id=row["subject_id"],
        book_id=row["book_id"],
        subject_code=row["subject_code"],
        syllabus_breakdown_id=syllabus_id,
    )


async def _cst_weekday_set(conn: asyncpg.Connection, cst_id: UUID) -> set[int]:
    """The CST's timetable weekdays (0=Mon..6=Sun). Default Mon-Fri if none set."""
    rows = await conn.fetch(
        "SELECT day_of_week FROM timetables WHERE cst_id = $1", cst_id
    )
    days = {r["day_of_week"] for r in rows}
    return days or {0, 1, 2, 3, 4}


async def chapter_slot_count(
    conn: asyncpg.Connection,
    cst_id: UUID,
    start_date: date | None,
    end_date: date | None,
) -> int:
    """
    D-9/D-14: slot count = number of real teaching periods in the chapter's
    date range = teaching days on the CST's timetable weekdays, minus holidays.
    Returns 0 if the chapter has no date range (admin hasn't set dates yet).

    F-1.4 (D-2/D-3/D-15): the holiday set is the union of the CST's effective
    holidays (org ± school ± CST, prior D-26) AND the dates reserved by the
    CST's published Syllabus Breakdown's exam periods + breakdown holidays. If
    the CST has no published breakdown, the extra sets are empty (graceful).
    """
    if start_date is None or end_date is None:
        return 0
    weekday_set = await _cst_weekday_set(conn, cst_id)
    holidays = await get_effective_holidays(conn, cst_id)
    ctx = await resolve_cst_syllabus_context(conn, cst_id)
    holidays = (
        holidays
        | await get_breakdown_exam_dates(conn, ctx.syllabus_breakdown_id)
        | await get_breakdown_holiday_dates(conn, ctx.syllabus_breakdown_id)
    )
    return len(compute_teaching_days(start_date, end_date, weekday_set, holidays))


# ---------------------------------------------------------------------------
# F2.1 — build a PlanRequest from the live connection (D-8)
# ---------------------------------------------------------------------------


async def build_plan_request(
    conn: asyncpg.Connection,
    *,
    book_chapter_id: UUID,
    subject: str,
    grade: int,
    period_count: int,
    curriculum: str = "ICT",
    mandatory_budget: int | None = None,
) -> PlanRequest:
    """
    Assemble a `PlanRequest` for one chapter from the live DB, reusing the query
    shape of the standalone CPE app's `db.get_chapter_as_plan_input`:

    - topics ordered by `topic_number`;
    - per-topic learning targets are the topic's sub-SLOs
      (`topic_sub_slos → sub_slos`) ordered by `position, code`;
    - the sub_slo UUID (as text) is the SLO `id` (unique across the chapter even
      when the same code appears on two topics; `PlanRequest` enforces unique
      SLO ids within a topic — we de-dup per topic);
    - the statement carries the human-readable `"[code] statement"` prefix.

    Uses the caller's live connection — does NOT open a second pool (D-8).
    Raises ValueError if the chapter isn't found.
    """
    chapter = await conn.fetchrow(
        "SELECT title FROM book_chapters WHERE id = $1", book_chapter_id
    )
    if chapter is None:
        raise ValueError(f"chapter {book_chapter_id} not found")

    topic_rows = await conn.fetch(
        """
        SELECT t.id::text AS topic_id, t.topic_text
          FROM topics t
         WHERE t.book_chapter_id = $1
         ORDER BY t.topic_number
        """,
        book_chapter_id,
    )

    topics: list[dict] = []
    for tr in topic_rows:
        slo_rows = await conn.fetch(
            """
            SELECT ss.id::text AS sub_slo_id, ss.code, ss.statement
              FROM topic_sub_slos tss
              JOIN sub_slos ss ON ss.id = tss.sub_slo_id
             WHERE tss.topic_id = $1::uuid
             ORDER BY ss.position, ss.code
            """,
            tr["topic_id"],
        )
        seen: set[str] = set()
        slos: list[dict] = []
        for sr in slo_rows:
            sid = sr["sub_slo_id"]
            if sid in seen:  # de-dup within a topic
                continue
            seen.add(sid)
            code = sr["code"] or ""
            statement = sr["statement"] or ""
            slos.append(
                {"id": sid, "statement": f"[{code}] {statement}" if code else statement}
            )
        topics.append(
            {"id": tr["topic_id"], "topic_text": tr["topic_text"] or "", "slos": slos}
        )

    return PlanRequest(
        subject=subject,
        grade=grade,
        curriculum=curriculum,
        period_count=period_count,
        mandatory_budget=mandatory_budget,
        chapter={"title": chapter["title"], "topics": topics},
    )


@dataclass
class GeneratePlanResult:
    cst_id: UUID
    book_chapter_id: UUID
    slot_count: int
    lesson_slot_count: int = 0
    assessment_slot_count: int = 0
    # dynamic-chapter-planner F-2.3: how many of the lesson slots are droppable
    # flex (revision) buffer slots. Subset of lesson_slot_count.
    flex_slot_count: int = 0
    warnings: list[str] = field(default_factory=list)
    # Provenance of the plan. 'cpe' = the intelligent Chapter Planner Engine
    # (the ported CPE planner now wired into break-it-down, D-1).
    source: str = "cpe"


async def generate_chapter_plan(
    conn: asyncpg.Connection,
    *,
    cst_id: UUID,
    book_chapter_id: UUID,
    org_id: UUID,
    llm: PlannerLLM | None = None,
) -> GeneratePlanResult:
    """
    F2.2 / "break it down" — generate a chapter's slots into the class slot
    tables for this CST, sized by the teacher's real timetable (D-9) and
    sequenced by the intelligent Chapter Planner (D-1).

    - slot_count = teaching periods in the chapter's class-path date range (the
      CST's `class_chapters` row, D-5/F1.6 — not the advisory global). It gates
      generation AND is the planner's `period_count`: the planner returns exactly
      `slot_count` Plan Units, so lesson_slot_count + assessment_slot_count ==
      slot_count.
    - For each Plan Unit, in `sequence` order, the persist branches on
      `unit.slot_type` (exam-periods-and-formative-assessments D-9, F-2.4):
      * 'lesson' → one `class_lesson_slot` (`slot_type='lesson'`,
        `lp_type=unit.lp_type`, lead `topic_id=unit.topic_ids[0]`,
        `book_chapter_id`, `status='planned'`) plus one `class_lesson_slot_topics`
        row per member topic (position 1..N, list order). The join table is the
        source of truth for the full topic grouping; `topic_id` is the lead topic
        for back-compat (D-9).
      * 'formative_assessment' → one `class_assessment_slot`
        (`assessment_type='formative'`, `book_chapter_id`, `status='scheduled'`)
        plus one `class_assessment_slot_topics` row per covered topic
        (position 1..N, list order). Bumps `result.assessment_slot_count`.
        No exam is generated here — that is Phase 3 (D-10/D-11).
    - Lessons and assessments share ONE global `position` sequence per CST so the
      projector merges both tables by position (1 slot = 1 teaching day, D-8/D-9).
    - This SUPERSEDES the prior chapter-planner-in-dars D-1 ("NO assessment slots
      are created") for the FA path. Summative slots are still NOT created
      (D-12/D-16).
    - No fallback (D-5): a planner failure (PlannerLLMError / PlanParseError /
      PlanValidationError) propagates to the caller.
    - Refuses (ValueError) if the chapter isn't in the class path, already has
      class slots for this CST, or has no date range yet (slot_count == 0).
    - `llm` is injectable for testing; defaults to `AgentSdkPlannerLLM()`.
    Caller does org/access checks.
    """
    log.info(
        "generate_chapter_plan: entry cst=%s chapter=%s org=%s",
        cst_id, book_chapter_id, org_id,
    )
    try:
        ctx = await resolve_cst_syllabus_context(conn, cst_id)

        # F1.6 (D-5): the chapter's dates come from the class's own teaching path
        # (`class_chapters`), set by the teacher (D-7) — not from the advisory
        # global `syllabus_chapters`. The chapter must be in the class path first.
        chapter = await conn.fetchrow(
            """
            SELECT start_date, end_date
            FROM class_chapters
            WHERE cst_id = $1 AND book_chapter_id = $2
            """,
            cst_id, book_chapter_id,
        )
        if chapter is None:
            raise ValueError(
                "chapter not in this class's plan; add it to your plan first"
            )

        slot_count = await chapter_slot_count(
            conn, cst_id, chapter["start_date"], chapter["end_date"]
        )
        if slot_count < 1:
            raise ValueError(
                "chapter has no teaching days in its date range "
                "(set the chapter's dates on the syllabus first)"
            )

        existing = await conn.fetchval(
            """
            SELECT
              (SELECT count(*) FROM class_lesson_slots
                 WHERE cst_id = $1 AND book_chapter_id = $2)
            + (SELECT count(*) FROM class_assessment_slots
                 WHERE cst_id = $1 AND book_chapter_id = $2)
            """,
            cst_id, book_chapter_id,
        )
        if existing:
            raise ValueError(
                "chapter already broken down; clear it first to regenerate"
            )

        result = GeneratePlanResult(
            cst_id=cst_id, book_chapter_id=book_chapter_id, slot_count=slot_count
        )

        # Grade number (PlanRequest wants an int 1..5); grades.code is that int.
        grade = await conn.fetchval(
            "SELECT code FROM grades WHERE id = $1", ctx.grade_id
        )
        if grade is None:
            raise ValueError(f"grade {ctx.grade_id} not found")

        # Buffer-budgeted planning (F-2.2/F-2.3, D-14/D-16): read the org's
        # completion target and split slot_count into a MANDATORY budget + a FLEX
        # buffer. The planner is asked to plan mandatory content into the budget
        # and interleave flex revision slots to reach slot_count (period_count).
        target = await conn.fetchval(
            "SELECT default_completion_target FROM organizations WHERE id = $1",
            org_id,
        )
        completion_target = (
            float(target) if target is not None else DEFAULT_COMPLETION_TARGET
        )
        mandatory_budget, flex_target = compute_buffer_budget(
            slot_count, completion_target
        )
        log.info(
            "generate_chapter_plan: budget cst=%s chapter=%s slot_count=%d "
            "target=%.2f mandatory=%d flex=%d",
            cst_id, book_chapter_id, slot_count, completion_target,
            mandatory_budget, flex_target,
        )

        # Build the planner input from the live connection (F2.1) and run the
        # intelligent planner (no fallback, D-5).
        request = await build_plan_request(
            conn,
            book_chapter_id=book_chapter_id,
            subject=ctx.subject_code,
            grade=int(grade),
            curriculum="ICT",
            period_count=slot_count,
            mandatory_budget=mandatory_budget,
        )
        plan = await make_chapter_plan(request, llm or AgentSdkPlannerLLM())

        async with conn.transaction():
            # Lessons + assessments share ONE global position sequence per CST
            # (the projector merges both tables by position; 1 slot = 1 day).
            pos = await conn.fetchval(
                """
                SELECT greatest(
                  (SELECT coalesce(max(position), 0) FROM class_lesson_slots WHERE cst_id = $1),
                  (SELECT coalesce(max(position), 0) FROM class_assessment_slots WHERE cst_id = $1)
                )
                """,
                cst_id,
            )

            # One slot per Plan Unit, in sequence order, branching on slot_type
            # (D-9). Lessons and FAs share the single incrementing `position`.
            for unit in sorted(plan.units, key=lambda u: u.sequence):
                pos += 1
                if unit.slot_type == "formative_assessment":
                    # FA → class_assessment_slots (assessment_type='formative',
                    # status='scheduled') + class_assessment_slot_topics for the
                    # covered topics. No lp_type, no exam yet (Phase 3, D-10/D-11).
                    slot_id = await conn.fetchval(
                        """
                        INSERT INTO class_assessment_slots
                          (org_id, cst_id, position, assessment_type,
                           book_chapter_id, status)
                        VALUES ($1, $2, $3, 'formative', $4, 'scheduled')
                        RETURNING id
                        """,
                        org_id, cst_id, pos, book_chapter_id,
                    )
                    for member_pos, t_id in enumerate(unit.topic_ids, start=1):
                        await conn.execute(
                            """
                            INSERT INTO class_assessment_slot_topics
                              (class_assessment_slot_id, topic_id, position)
                            VALUES ($1, $2, $3)
                            """,
                            slot_id, UUID(t_id), member_pos,
                        )
                    result.assessment_slot_count += 1
                    continue

                # lesson → class_lesson_slots (+ class_lesson_slot_topics). The
                # join table records the full topic grouping; topic_id is the
                # lead topic for back-compat. A flex unit (F-2.1/F-2.3, D-15) is
                # persisted with flex=true; every break-it-down slot is seeded so
                # origin='breakdown' (D-1).
                lead_topic_id = UUID(unit.topic_ids[0])
                slot_id = await conn.fetchval(
                    """
                    INSERT INTO class_lesson_slots
                      (org_id, cst_id, position, slot_type, lp_type, topic_id,
                       book_chapter_id, status, origin, flex)
                    VALUES ($1, $2, $3, 'lesson', $4, $5, $6, 'planned',
                            'breakdown', $7)
                    RETURNING id
                    """,
                    org_id, cst_id, pos, unit.lp_type, lead_topic_id,
                    book_chapter_id, unit.flex,
                )
                for member_pos, t_id in enumerate(unit.topic_ids, start=1):
                    await conn.execute(
                        """
                        INSERT INTO class_lesson_slot_topics
                          (class_lesson_slot_id, topic_id, position)
                        VALUES ($1, $2, $3)
                        """,
                        slot_id, UUID(t_id), member_pos,
                    )
                result.lesson_slot_count += 1
                if unit.flex:
                    result.flex_slot_count += 1

        log.info(
            "generate_chapter_plan: exit cst=%s chapter=%s lessons=%d "
            "(flex=%d) assessments=%d source=%s",
            cst_id, book_chapter_id, result.lesson_slot_count,
            result.flex_slot_count, result.assessment_slot_count, result.source,
        )
        return result
    except Exception:
        log.error(
            "generate_chapter_plan: error cst=%s chapter=%s", cst_id, book_chapter_id,
            exc_info=True,
        )
        raise
