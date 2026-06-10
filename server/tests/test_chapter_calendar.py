"""Phase 1 (chapter-breakdown-and-plan) — pure chapter-calendar unit tests (no DB)."""
from datetime import date
from uuid import uuid4

from dars.breakdown.chapter_calendar import (
    compute_range_warnings,
    derived_teaching_days,
    expand_ranges,
)


def test_derived_teaching_days_counts_weekdays_minus_holidays():
    # 2026-06-08 (Mon) .. 2026-06-12 (Fri): 5 weekdays; one holiday.
    n = derived_teaching_days(
        date(2026, 6, 8), date(2026, 6, 12), holidays={date(2026, 6, 10)}
    )
    assert n == 4


def test_derived_teaching_days_none_without_range():
    assert derived_teaching_days(None, date(2026, 6, 12), holidays=set()) is None
    assert derived_teaching_days(date(2026, 6, 8), None, holidays=set()) is None


def test_warnings_overlap():
    a, b = uuid4(), uuid4()
    chapters = [
        {"id": a, "position": 1, "start_date": date(2026, 6, 8), "end_date": date(2026, 6, 19)},
        {"id": b, "position": 2, "start_date": date(2026, 6, 15), "end_date": date(2026, 6, 26)},
    ]
    warnings = compute_range_warnings(chapters, holidays=set())
    assert {"type": "overlap", "chapter_ids": [a, b]} in warnings


def test_warnings_gap():
    a, b = uuid4(), uuid4()
    chapters = [
        {"id": a, "position": 1, "start_date": date(2026, 6, 8), "end_date": date(2026, 6, 12)},
        {"id": b, "position": 2, "start_date": date(2026, 6, 22), "end_date": date(2026, 6, 26)},
    ]
    warnings = compute_range_warnings(chapters, holidays=set())
    assert {"type": "gap", "chapter_ids": [a, b]} in warnings


def test_warnings_no_gap_when_consecutive():
    a, b = uuid4(), uuid4()
    # a ends Fri 6/12; b starts Mon 6/15 — no teaching day between them.
    chapters = [
        {"id": a, "position": 1, "start_date": date(2026, 6, 8), "end_date": date(2026, 6, 12)},
        {"id": b, "position": 2, "start_date": date(2026, 6, 15), "end_date": date(2026, 6, 19)},
    ]
    warnings = compute_range_warnings(chapters, holidays=set())
    assert warnings == []


def test_warnings_zero_teaching_days():
    a = uuid4()
    # 2026-06-13 (Sat) .. 2026-06-14 (Sun): weekend only.
    chapters = [
        {"id": a, "position": 1, "start_date": date(2026, 6, 13), "end_date": date(2026, 6, 14)},
    ]
    warnings = compute_range_warnings(chapters, holidays=set())
    assert {"type": "zero_teaching_days", "chapter_ids": [a]} in warnings


def test_warnings_skip_undated_chapters():
    a = uuid4()
    chapters = [{"id": a, "position": 1, "start_date": None, "end_date": None}]
    assert compute_range_warnings(chapters, holidays=set()) == []


# ---------------------------------------------------------------------------
# F-1.2 — expand_ranges (exam periods + breakdown holidays), pure (no DB)
# ---------------------------------------------------------------------------


def test_expand_ranges_empty():
    assert expand_ranges([]) == set()


def test_expand_ranges_single_day():
    rows = [{"start_date": date(2026, 8, 1), "end_date": date(2026, 8, 1)}]
    assert expand_ranges(rows) == {date(2026, 8, 1)}


def test_expand_ranges_multi_day_inclusive():
    rows = [{"start_date": date(2026, 8, 1), "end_date": date(2026, 8, 3)}]
    assert expand_ranges(rows) == {
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
    }


def test_expand_ranges_unions_and_dedups_overlapping():
    rows = [
        {"start_date": date(2026, 8, 1), "end_date": date(2026, 8, 3)},
        {"start_date": date(2026, 8, 3), "end_date": date(2026, 8, 4)},
    ]
    assert expand_ranges(rows) == {
        date(2026, 8, 1),
        date(2026, 8, 2),
        date(2026, 8, 3),
        date(2026, 8, 4),
    }


def test_expand_ranges_inverted_range_contributes_nothing():
    rows = [{"start_date": date(2026, 8, 5), "end_date": date(2026, 8, 1)}]
    assert expand_ranges(rows) == set()


def test_expand_ranges_skips_rows_with_null_bounds():
    rows = [
        {"start_date": None, "end_date": date(2026, 8, 1)},
        {"start_date": date(2026, 8, 2), "end_date": None},
        {"start_date": date(2026, 8, 3), "end_date": date(2026, 8, 3)},
    ]
    assert expand_ranges(rows) == {date(2026, 8, 3)}


# ---------------------------------------------------------------------------
# F-1.3 — admin derivation reduced by an exam/holiday window (D-2/D-4)
#
# This exercises the exact data flow _hydrate_breakdown uses: expand the
# breakdown's ranges, then feed the union into derived_teaching_days /
# compute_range_warnings. Pure (no DB).
# ---------------------------------------------------------------------------


def test_admin_derivation_reduced_by_exam_period():
    # Chapter 2026-08-03 (Mon) .. 2026-08-07 (Fri) = 5 teaching days.
    # An exam period 2026-08-05..08-06 removes 2 of them -> 3 left.
    exam_rows = [{"start_date": date(2026, 8, 5), "end_date": date(2026, 8, 6)}]
    holidays = expand_ranges(exam_rows)
    n = derived_teaching_days(date(2026, 8, 3), date(2026, 8, 7), holidays)
    assert n == 3
    # Without the exam period it would be the full 5 (regression baseline).
    assert derived_teaching_days(date(2026, 8, 3), date(2026, 8, 7), set()) == 5


def test_admin_zero_teaching_days_when_chapter_inside_exam_window():
    a = uuid4()
    # Chapter fully inside an exam period -> zero teaching days warning (D-4).
    exam_rows = [{"start_date": date(2026, 8, 3), "end_date": date(2026, 8, 7)}]
    holidays = expand_ranges(exam_rows)
    chapters = [
        {"id": a, "position": 1, "start_date": date(2026, 8, 3), "end_date": date(2026, 8, 7)},
    ]
    warnings = compute_range_warnings(chapters, holidays)
    assert {"type": "zero_teaching_days", "chapter_ids": [a]} in warnings


def test_admin_no_ranges_behaves_as_before():
    # Regression: empty exam + holiday rows => empty exclusion set => unchanged.
    holidays = expand_ranges([]) | expand_ranges([])
    assert holidays == set()
    assert derived_teaching_days(date(2026, 8, 3), date(2026, 8, 7), holidays) == 5
