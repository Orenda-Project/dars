"""F2.8 — pure projector unit tests (no DB)."""
from datetime import date
from uuid import uuid4

from dars.breakdown.projector import (
    SlotInput,
    compute_teaching_days,
    project_schedule,
)


def _slot(position: int, anchor: date | None = None, kind: str = "lesson") -> SlotInput:
    return SlotInput(slot_id=uuid4(), slot_kind=kind, position=position, anchor_date=anchor)


def test_compute_teaching_days_mon_fri():
    # 2026-05-04 is a Monday.
    days = compute_teaching_days(
        date(2026, 5, 4), date(2026, 5, 10),
        weekday_set={0, 1, 2, 3, 4},
        holidays=set(),
    )
    assert days == [
        date(2026, 5, 4), date(2026, 5, 5), date(2026, 5, 6),
        date(2026, 5, 7), date(2026, 5, 8),
    ]  # Mon-Fri only; weekend skipped.


def test_compute_teaching_days_skips_holidays():
    days = compute_teaching_days(
        date(2026, 5, 4), date(2026, 5, 8),
        weekday_set={0, 1, 2, 3, 4},
        holidays={date(2026, 5, 6)},  # Wednesday holiday
    )
    assert date(2026, 5, 6) not in days
    assert len(days) == 4


def test_compute_teaching_days_handles_inverted_range():
    days = compute_teaching_days(
        date(2026, 5, 10), date(2026, 5, 4),
        weekday_set={0, 1, 2, 3, 4},
        holidays=set(),
    )
    assert days == []


def test_project_no_anchors_uses_sequential_teaching_days():
    teaching = [date(2026, 5, d) for d in (4, 5, 6, 7, 8)]
    slots = [_slot(p) for p in range(1, 4)]
    out = project_schedule(slots, teaching)
    assert [p.projected_date for p in out] == teaching[:3]
    assert all(not p.is_anchor and not p.is_overflow and not p.is_conflict for p in out)


def test_project_overflow_when_more_slots_than_days():
    teaching = [date(2026, 5, 4), date(2026, 5, 5)]
    slots = [_slot(p) for p in range(1, 5)]
    out = project_schedule(slots, teaching)
    assert out[0].projected_date == date(2026, 5, 4)
    assert out[1].projected_date == date(2026, 5, 5)
    # Slots 3 and 4 overflow.
    assert out[2].is_overflow is True and out[2].projected_date is None
    assert out[3].is_overflow is True


def test_project_anchor_in_teaching_set_consumes_prior_days():
    teaching = [date(2026, 5, d) for d in (4, 5, 6, 7, 8, 11, 12)]
    # 5 slots; slot 3 is anchored on 2026-05-08 (Friday).
    slots = [_slot(1), _slot(2), _slot(3, anchor=date(2026, 5, 8)), _slot(4), _slot(5)]
    out = project_schedule(slots, teaching)
    assert out[0].projected_date == date(2026, 5, 4)
    assert out[1].projected_date == date(2026, 5, 5)
    assert out[2].projected_date == date(2026, 5, 8) and out[2].is_anchor
    # Subsequent slots resume *after* the anchor.
    assert out[3].projected_date == date(2026, 5, 11)
    assert out[4].projected_date == date(2026, 5, 12)


def test_project_anchor_on_non_teaching_day_flags_conflict():
    teaching = [date(2026, 5, d) for d in (4, 5, 7, 8)]  # Wed (5/6) is a holiday
    slots = [_slot(1, anchor=date(2026, 5, 6))]  # anchor lands on the holiday
    out = project_schedule(slots, teaching)
    assert out[0].is_conflict is True
    assert out[0].is_anchor is True
    assert out[0].projected_date == date(2026, 5, 6)
    # The conflict anchor should not consume teaching days; next slot would
    # still start at 5/4 if there were a next slot.


# ---------------------------------------------------------------------------
# F-1.4 — exam/holiday dates excluded from the teaching-day list mean no slot
# is ever projected inside an exam/holiday window (D-2). The DB wrapper unions
# breakdown exam+holiday dates into `holidays` before compute_teaching_days; we
# pin that composition here purely (no DB).
# ---------------------------------------------------------------------------


def test_project_never_lands_slot_inside_exam_window():
    from dars.breakdown.chapter_calendar import expand_ranges

    # Mon 2026-05-04 .. Fri 2026-05-15 (two Mon-Fri weeks = 10 weekdays).
    # Exam period 2026-05-06..05-08 (Wed-Fri week 1) removes 3 teaching days.
    exam_dates = expand_ranges(
        [{"start_date": date(2026, 5, 6), "end_date": date(2026, 5, 8)}]
    )
    teaching = compute_teaching_days(
        date(2026, 5, 4), date(2026, 5, 15),
        weekday_set={0, 1, 2, 3, 4},
        holidays=exam_dates,
    )
    # 10 weekdays minus the 3 exam weekdays = 7 teaching days.
    assert len(teaching) == 7
    assert exam_dates.isdisjoint(teaching)

    slots = [_slot(p) for p in range(1, 8)]
    out = project_schedule(slots, teaching, holidays=exam_dates)
    projected = {p.projected_date for p in out}
    # No slot is projected on any exam date.
    assert projected.isdisjoint(exam_dates)
    assert all(not p.is_overflow for p in out)
