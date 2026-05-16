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
