"""
Chapter-Breakdown calendar helpers (chapter-breakdown-and-plan, Phase 1).

Derives teaching-day counts for a chapter's explicit date range (D-2) and
computes advisory range warnings (D-5, non-blocking).

Calendar source per D-5/decision: weekdays Mon-Fri in the range minus
org_holidays for the breakdown's academic year. A breakdown is
global/org/class-scoped and has no CST, so we resolve the academic year
best-effort by the breakdown's org; for global-scope breakdowns (no org)
we fall back to plain Mon-Fri (no holidays).

Reuses `projector.compute_teaching_days` verbatim for the day walk.
"""
import logging
from datetime import date
from uuid import UUID

import asyncpg

from dars.breakdown.projector import compute_teaching_days

log = logging.getLogger("breakdown.chapter_calendar")

# Mon-Fri (0=Monday .. 6=Sunday, matching date.weekday()).
WEEKDAY_SET: set[int] = {0, 1, 2, 3, 4}


async def resolve_breakdown_holidays(
    conn: asyncpg.Connection, breakdown_id: UUID
) -> set[date]:
    """
    Holiday set for a syllabus breakdown's academic calendar.

    Syllabus breakdowns are global-only (Phase 2): they are not bound to any
    org or academic year, so there are no holidays to subtract. Callers count
    plain weekdays (Mon-Fri). Kept async + signature-stable so call sites and
    any future per-org calendar work don't have to change.
    """
    return set()


def derived_teaching_days(
    start_date: date | None,
    end_date: date | None,
    holidays: set[date],
) -> int | None:
    """Count teaching days (Mon-Fri minus holidays) in [start, end]. None if no range."""
    if start_date is None or end_date is None:
        return None
    return len(compute_teaching_days(start_date, end_date, WEEKDAY_SET, holidays))


def compute_range_warnings(chapters: list[dict], holidays: set[date]) -> list[dict]:
    """
    Advisory, non-blocking warnings across a breakdown's dated chapters (D-5).

    Emits, ordered by chapter position:
      - {"type": "overlap", "chapter_ids": [a, b]} when two ranges intersect
      - {"type": "gap", "chapter_ids": [a, b]} when a teaching-day gap sits
        between consecutive dated chapters
      - {"type": "zero_teaching_days", "chapter_ids": [a]} when a dated range
        contains no teaching days

    `chapters` items need: id, position, start_date, end_date.
    Chapters without a full date range are skipped for overlap/gap checks.
    """
    warnings: list[dict] = []
    dated = sorted(
        [c for c in chapters if c.get("start_date") and c.get("end_date")],
        key=lambda c: (c["start_date"], c["position"]),
    )

    for c in dated:
        if derived_teaching_days(c["start_date"], c["end_date"], holidays) == 0:
            warnings.append({"type": "zero_teaching_days", "chapter_ids": [c["id"]]})

    for prev, cur in zip(dated, dated[1:]):
        if cur["start_date"] <= prev["end_date"]:
            warnings.append({"type": "overlap", "chapter_ids": [prev["id"], cur["id"]]})
        else:
            # teaching days strictly between prev.end and cur.start
            between = compute_teaching_days(
                _next_day(prev["end_date"]),
                _prev_day(cur["start_date"]),
                WEEKDAY_SET,
                holidays,
            )
            if between:
                warnings.append({"type": "gap", "chapter_ids": [prev["id"], cur["id"]]})

    log.info(
        "compute_range_warnings: dated=%d warnings=%d", len(dated), len(warnings)
    )
    return warnings


def _next_day(d: date) -> date:
    from datetime import timedelta

    return d + timedelta(days=1)


def _prev_day(d: date) -> date:
    from datetime import timedelta

    return d - timedelta(days=1)
