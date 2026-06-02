"""F3.2 — slot-count = real teaching periods in a chapter's date range (D-9/D-14).

The slot count is exactly len(compute_teaching_days(start, end, weekdays, holidays)).
These tests pin that formula (the async DB wrapper chapter_slot_count just feeds
the CST's timetable weekdays + effective holidays into this)."""
from datetime import date

from dars.breakdown.projector import compute_teaching_days

MON_FRI = {0, 1, 2, 3, 4}


def _count(start, end, weekdays=MON_FRI, holidays=frozenset()):
    return len(compute_teaching_days(start, end, weekdays, set(holidays)))


def test_full_weeks_mon_fri():
    # 2026-06-01 (Mon) .. 2026-06-26 (Fri) = 4 full Mon-Fri weeks = 20.
    assert _count(date(2026, 6, 1), date(2026, 6, 26)) == 20


def test_partial_week_ends():
    # Wed 2026-06-03 .. Tue 2026-06-09: Wed,Thu,Fri + Mon,Tue = 5.
    assert _count(date(2026, 6, 3), date(2026, 6, 9)) == 5


def test_holiday_reduces_count():
    # 2026-06-01..05 (Mon-Fri) = 5; minus one holiday = 4.
    assert _count(date(2026, 6, 1), date(2026, 6, 5)) == 5
    assert _count(date(2026, 6, 1), date(2026, 6, 5), holidays={date(2026, 6, 3)}) == 4


def test_custom_timetable_mon_wed_fri():
    # Class meets Mon/Wed/Fri only, over 2026-06-01..14 (two weeks) = 6.
    assert _count(date(2026, 6, 1), date(2026, 6, 14), weekdays={0, 2, 4}) == 6


def test_weekend_only_range_is_zero():
    # Sat 2026-06-06 .. Sun 2026-06-07, Mon-Fri class = 0 teaching days.
    assert _count(date(2026, 6, 6), date(2026, 6, 7)) == 0
