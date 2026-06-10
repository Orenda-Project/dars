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


# ---------------------------------------------------------------------------
# F-1.4 — breakdown exam + holiday dates union ADDITIVELY into the holiday set
# that chapter_slot_count feeds to compute_teaching_days (D-2/D-3/D-15). The
# org/school/CST effective holidays still apply (prior D-26 intact). Pure: we
# pin the set-union -> count composition the DB wrapper performs.
# ---------------------------------------------------------------------------


def test_breakdown_exam_dates_reduce_slot_count():
    from dars.breakdown.chapter_calendar import expand_ranges

    # 2026-06-01 (Mon) .. 06-05 (Fri) = 5 teaching days, no other holidays.
    exam = expand_ranges([{"start_date": date(2026, 6, 3), "end_date": date(2026, 6, 4)}])
    effective = set()  # no org/school/CST holidays
    holidays = effective | exam
    assert _count(date(2026, 6, 1), date(2026, 6, 5), holidays=holidays) == 3


def test_breakdown_dates_additive_to_effective_holidays():
    from dars.breakdown.chapter_calendar import expand_ranges

    # Effective (org) holiday on Mon 06-01; breakdown holiday range 06-04..05.
    # Both apply: 5 weekdays - 1 org - 2 breakdown = 2.
    effective = {date(2026, 6, 1)}
    breakdown_hol = expand_ranges(
        [{"start_date": date(2026, 6, 4), "end_date": date(2026, 6, 5)}]
    )
    holidays = effective | breakdown_hol
    assert _count(date(2026, 6, 1), date(2026, 6, 5), holidays=holidays) == 2


def test_no_breakdown_dates_is_unchanged():
    from dars.breakdown.chapter_calendar import expand_ranges

    # Regression: empty breakdown sets => count equals the effective-only count.
    effective = {date(2026, 6, 3)}
    holidays = effective | expand_ranges([]) | expand_ranges([])
    assert _count(date(2026, 6, 1), date(2026, 6, 5), holidays=holidays) == 4
    assert _count(date(2026, 6, 1), date(2026, 6, 5), holidays=effective) == 4
