"""
Reteach trigger — Dynamic Chapter Planner, Phase 3 (F-3.1, F-3.2, D-5/D-9/D-10/D-17).

A graded Formative Assessment whose per-sub-SLO mastery falls below
`RETEACH_MASTERY_THRESHOLD` SUGGESTS a reteach (F-3.1). Reteach is never
auto-applied (D-9): the teacher confirms an explicit action (F-3.2):

  * lightweight (default) — flip `cst_sub_slo_coverage` for the sub-SLO to
    'not_taught' (needs-rework / fold into the next class). No new slot, no
    position shift.
  * heavy — consume the nearest downstream FLEX slot in place
    (`consume_flex_slot`, no shift, D-5); if none exists, insert a new lesson
    slot (`insert_lesson_slot`, shifts the tail) AND compute the overflow
    consequence (does inserting push a tail slot out of the year-end? which
    position? — D-17, via a projector dry-run delta). Either way the reteach
    slot rides the shipped on-demand LP path (`get_or_generate_lp`) with
    `lp_type='revision'`, `origin='reteach'`, `reteach_for_sub_slo_id` set
    (D-10).

All DB-touching mutation SQL is portable (asyncpg `$N`) so the consume-vs-insert
branch + consequence logic is exercised against sqlite with no DATABASE_URL
(D-11). The projector is injectable so the consequence math can be unit-tested
with a fake.

Structured logging per CLAUDE.md rule 11: entry/exit at INFO with the slot +
sub-SLO ids and the path chosen; errors at ERROR with exc_info=True.
"""
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

from dars.breakdown.slot_mutation_service import (
    consume_flex_slot,
    insert_lesson_slot,
)

log = logging.getLogger("breakdown.reteach")

# F-3.1: a sub-SLO whose class mastery is strictly below this fires a reteach
# suggestion. Module-level constant (not a column, per 02-data-model.md Phase 3).
# 60.0 = "fewer than ~3 in 5 students got it" — the class struggled.
RETEACH_MASTERY_THRESHOLD = 60.0

# Reteach LP rides the shipped on-demand path as a revision LP (D-10).
RETEACH_LP_TYPE = "revision"


# ---------------------------------------------------------------------------
# F-3.1 — suggestion read (no mutation)
# ---------------------------------------------------------------------------


@dataclass
class ReteachSuggestion:
    """One below-threshold sub-SLO surfaced against a graded FA slot."""
    sub_slo_id: UUID
    sub_slo_code: str
    statement: str
    mastery_percent: float


async def suggest_reteach(
    conn, class_assessment_slot_id: UUID
) -> list[ReteachSuggestion]:
    """
    For a graded formative-assessment slot, return the sub-SLOs whose recorded
    `sub_slo_mastery.mastery_percent` is below `RETEACH_MASTERY_THRESHOLD`
    (F-3.1). This is the suggestion payload for the teacher-app badge — a read
    only, no mutation.

    Returns an empty list when the slot has no graded mastery yet or every
    sub-SLO is at/above threshold. Raises ValueError if the slot isn't a
    formative assessment.
    """
    log.info(
        "suggest_reteach: entry slot=%s threshold=%.1f",
        class_assessment_slot_id, RETEACH_MASTERY_THRESHOLD,
    )
    slot = await conn.fetchrow(
        "SELECT assessment_type FROM class_assessment_slots WHERE id = $1",
        class_assessment_slot_id,
    )
    if slot is None:
        raise ValueError(
            f"class_assessment_slot {class_assessment_slot_id} not found"
        )
    if slot["assessment_type"] != "formative":
        raise ValueError(
            f"slot {class_assessment_slot_id} is not a formative assessment "
            f"(got {slot['assessment_type']!r}); reteach suggestions are FA-only"
        )

    rows = await conn.fetch(
        """
        SELECT ssm.sub_slo_id      AS sub_slo_id,
               ss.code             AS sub_slo_code,
               ss.statement        AS statement,
               ssm.mastery_percent AS mastery_percent
          FROM sub_slo_mastery ssm
          JOIN sub_slos ss ON ss.id = ssm.sub_slo_id
         WHERE ssm.class_assessment_slot_id = $1
           AND ssm.mastery_percent < $2
         ORDER BY ssm.mastery_percent, ss.code
        """,
        class_assessment_slot_id, RETEACH_MASTERY_THRESHOLD,
    )
    out = [
        ReteachSuggestion(
            sub_slo_id=r["sub_slo_id"],
            sub_slo_code=r["sub_slo_code"],
            statement=r["statement"],
            mastery_percent=float(r["mastery_percent"]),
        )
        for r in rows
    ]
    log.info(
        "suggest_reteach: exit slot=%s below_threshold=%d",
        class_assessment_slot_id, len(out),
    )
    return out


# ---------------------------------------------------------------------------
# F-3.2 — reteach actions (teacher-confirmed mutation, D-9)
# ---------------------------------------------------------------------------


@dataclass
class OverflowConsequence:
    """The year-end consequence of inserting a reteach slot (D-17).

    Computed as a projector dry-run delta around the insert: which tail slots
    NEWLY overflow because the inserted slot shifted them past the academic
    year's last teaching day.
    """
    overflow_before: int
    overflow_after: int
    newly_overflowed_positions: list[int]
    first_overflow_position: int | None


@dataclass
class ReteachResult:
    """Outcome of a confirmed reteach action.

    path:
      'lightweight'  — coverage flipped to needs-rework; no slot, no shift.
      'consume_flex' — a downstream flex slot was repurposed in place (no shift).
      'insert'       — a new lesson slot was inserted (tail shifted by one).
    slot_id is the reteach lesson slot for the heavy paths, None for lightweight.
    consequence is populated only for 'insert' (the path that can overflow);
    None for 'lightweight' and 'consume_flex' (neither shifts the tail).
    """
    path: str
    slot_id: UUID | None
    consequence: OverflowConsequence | None = None


# A projector returns objects carrying `.position` and `.is_overflow`. The real
# one is `projector.project_cst_schedule`; tests inject a fake.
ProjectorFn = Callable[..., Awaitable[list]]


async def _overflow_positions(projector: ProjectorFn, conn, cst_id: UUID) -> set[int]:
    """The set of slot positions the projector flags as overflow right now."""
    projected = await projector(conn, cst_id)
    return {p.position for p in projected if getattr(p, "is_overflow", False)}


async def _resolve_reteach_topic(conn, book_chapter_id, sub_slo_id: UUID) -> UUID:
    """
    The topic to hang the reteach LP on: a topic of the failed sub-SLO that
    belongs to the FA slot's chapter (so the revision LP keys on the right
    chapter content). A sub-SLO may sit on several topics; pick the chapter's
    lowest topic_number for determinism. Falls back to any topic carrying the
    sub-SLO if the chapter link is missing. Raises ValueError if none exists.
    """
    row = await conn.fetchrow(
        """
        SELECT t.id AS topic_id
          FROM topic_sub_slos tss
          JOIN topics t ON t.id = tss.topic_id
         WHERE tss.sub_slo_id = $1
           AND t.book_chapter_id = $2
         ORDER BY t.topic_number
         LIMIT 1
        """,
        sub_slo_id, book_chapter_id,
    )
    if row is None:
        row = await conn.fetchrow(
            """
            SELECT t.id AS topic_id
              FROM topic_sub_slos tss
              JOIN topics t ON t.id = tss.topic_id
             WHERE tss.sub_slo_id = $1
             ORDER BY t.topic_number
             LIMIT 1
            """,
            sub_slo_id,
        )
    if row is None:
        raise ValueError(
            f"sub_slo {sub_slo_id} has no topic; cannot build a reteach lesson"
        )
    return row["topic_id"]


async def reteach(
    conn,
    *,
    class_assessment_slot_id: UUID,
    sub_slo_id: UUID,
    mode: str = "lightweight",
    lp_generator: Callable[..., Awaitable] | None = None,
    projector: ProjectorFn | None = None,
) -> ReteachResult:
    """
    Apply a teacher-confirmed reteach for one below-threshold sub-SLO against a
    graded FA slot (F-3.2, D-5/D-9/D-10/D-17). `mode` is the explicit teacher
    choice — there is no auto-apply.

      mode='lightweight' (default): flip `cst_sub_slo_coverage` for
        (cst_id, sub_slo_id) to 'not_taught'. No slot, no shift.

      mode='heavy': consume the nearest downstream flex slot in place; if none,
        insert a new lesson slot after the FA and compute the overflow
        consequence (D-17). The reteach slot then gets its LP via the injected
        `lp_generator` (defaults to generated_lps.service.get_or_generate_lp),
        carrying lp_type='revision', origin='reteach', reteach_for_sub_slo_id.

    `projector` defaults to `projector.project_cst_schedule` (injectable for
    tests). `lp_generator(conn, slot_id)` defaults to the shipped on-demand LP
    path; injectable so tests don't dispatch to LP Assistant.

    Raises ValueError on a bad mode, a missing/non-FA slot, or an unresolvable
    reteach topic.
    """
    log.info(
        "reteach: entry slot=%s sub_slo=%s mode=%s",
        class_assessment_slot_id, sub_slo_id, mode,
    )
    if mode not in ("lightweight", "heavy"):
        raise ValueError(f"mode must be 'lightweight' or 'heavy' (got {mode!r})")

    try:
        fa = await conn.fetchrow(
            """
            SELECT cst_id, position, assessment_type, book_chapter_id
              FROM class_assessment_slots
             WHERE id = $1
            """,
            class_assessment_slot_id,
        )
        if fa is None:
            raise ValueError(
                f"class_assessment_slot {class_assessment_slot_id} not found"
            )
        if fa["assessment_type"] != "formative":
            raise ValueError(
                f"slot {class_assessment_slot_id} is not a formative assessment"
            )
        cst_id = fa["cst_id"]
        after_position = fa["position"]
        book_chapter_id = fa["book_chapter_id"]

        # --- Lightweight (default): coverage flip only, no slot, no shift. ---
        if mode == "lightweight":
            async with conn.transaction():
                await conn.execute(
                    """
                    INSERT INTO cst_sub_slo_coverage
                        (cst_id, sub_slo_id, status, marked_at)
                    VALUES ($1, $2, 'not_taught', now())
                    ON CONFLICT (cst_id, sub_slo_id) DO UPDATE
                        SET status = 'not_taught', marked_at = now()
                    """,
                    cst_id, sub_slo_id,
                )
            log.info(
                "reteach: exit slot=%s sub_slo=%s path=lightweight",
                class_assessment_slot_id, sub_slo_id,
            )
            return ReteachResult(path="lightweight", slot_id=None)

        # --- Heavy: consume flex first (D-5), else insert + consequence. ---
        topic_id = await _resolve_reteach_topic(conn, book_chapter_id, sub_slo_id)

        slot_id = await consume_flex_slot(
            conn, cst_id, after_position,
            reteach_for_sub_slo_id=sub_slo_id,
            lp_type=RETEACH_LP_TYPE,
            topic_ids=[topic_id],
        )
        if slot_id is not None:
            # Consume shifts nothing — no overflow consequence (D-17).
            path = "consume_flex"
            consequence = None
        else:
            # No downstream flex — insert (shifts the tail). Measure the
            # overflow delta around the mutation via a projector dry run (D-17).
            from dars.breakdown.projector import project_cst_schedule
            proj = projector or project_cst_schedule

            before = await _overflow_positions(proj, conn, cst_id)
            slot_id = await insert_lesson_slot(
                conn, cst_id, after_position,
                topic_ids=[topic_id],
                lp_type=RETEACH_LP_TYPE,
                origin="reteach",
                reteach_for_sub_slo_id=sub_slo_id,
                flex=False,
            )
            after = await _overflow_positions(proj, conn, cst_id)
            newly = sorted(after - before)
            consequence = OverflowConsequence(
                overflow_before=len(before),
                overflow_after=len(after),
                newly_overflowed_positions=newly,
                first_overflow_position=(newly[0] if newly else None),
            )
            path = "insert"

        # Reteach slot rides the shipped on-demand LP path (D-10). Wrapped so a
        # generation hiccup doesn't undo the (already-committed) mutation — the
        # slot exists; the teacher app can re-request the LP. Default generator
        # is imported lazily to avoid a generated_lps <-> breakdown import cycle.
        if lp_generator is None:
            from dars.generated_lps.service import get_or_generate_lp as _gen
            lp_generator = _gen
        try:
            await lp_generator(conn, slot_id)
        except Exception:
            log.error(
                "reteach: LP generation failed for reteach slot=%s "
                "(mutation already applied; LP is re-requestable)",
                slot_id, exc_info=True,
            )

        log.info(
            "reteach: exit slot=%s sub_slo=%s path=%s reteach_slot=%s "
            "overflow_after=%s",
            class_assessment_slot_id, sub_slo_id, path, slot_id,
            (consequence.overflow_after if consequence else None),
        )
        return ReteachResult(path=path, slot_id=slot_id, consequence=consequence)
    except Exception:
        log.error(
            "reteach: error slot=%s sub_slo=%s mode=%s",
            class_assessment_slot_id, sub_slo_id, mode, exc_info=True,
        )
        raise
