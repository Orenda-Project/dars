"""Phase 1 (chapter-breakdown-and-plan) — pure chapter-calendar unit tests (no DB)."""
from datetime import date
from uuid import uuid4

from dars.breakdown.chapter_calendar import (
    compute_range_warnings,
    derived_teaching_days,
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
