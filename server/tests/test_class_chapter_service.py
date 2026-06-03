"""
Class-chapter path — pure-logic tests (no DB).

Covers the two extracted pure helpers that carry the feature's non-trivial
logic: status derivation (D-4) and the reorder lock (D-6). The DB-facing path
ops (pick/set-dates/remove/reorder/recommended-next) are thin wrappers over
these + SQL and are exercised by the DB-gated suite / e2e.
"""
from uuid import uuid4

import pytest

from dars.breakdown.class_chapter_service import (
    STATUS_DONE,
    STATUS_IN_PROGRESS,
    STATUS_YET_TO_START,
    derive_chapter_status,
    validate_reorder,
)


# ---------------------------------------------------------------------------
# Status derivation (D-4)
# ---------------------------------------------------------------------------


def test_status_no_slots_is_yet_to_start():
    # Picked but not broken down → no slots → yet_to_start.
    assert derive_chapter_status([]) == STATUS_YET_TO_START


def test_status_all_planned_is_yet_to_start():
    # Broken down but nothing taught yet → all non-terminal → yet_to_start.
    assert derive_chapter_status(["planned", "planned", "scheduled"]) == STATUS_YET_TO_START


def test_status_some_terminal_is_in_progress():
    assert derive_chapter_status(["taught", "planned", "scheduled"]) == STATUS_IN_PROGRESS


def test_status_one_terminal_among_many_is_in_progress():
    assert derive_chapter_status(["planned", "planned", "completed"]) == STATUS_IN_PROGRESS


def test_status_all_terminal_is_done():
    # Mix of terminal kinds across lesson + assessment slots.
    assert derive_chapter_status(["taught", "completed", "skipped"]) == STATUS_DONE


def test_status_single_terminal_slot_is_done():
    # >= 1 slot, all terminal → done.
    assert derive_chapter_status(["taught"]) == STATUS_DONE


def test_status_skipped_counts_as_terminal():
    # A fully-skipped chapter is 'done' for status purposes (a decision was made).
    assert derive_chapter_status(["skipped", "skipped"]) == STATUS_DONE


def test_status_skipped_partial_is_in_progress():
    assert derive_chapter_status(["skipped", "planned"]) == STATUS_IN_PROGRESS


# ---------------------------------------------------------------------------
# Reorder lock (D-6)
# ---------------------------------------------------------------------------


def _ids(n: int):
    return [uuid4() for _ in range(n)]


def test_reorder_all_yet_to_start_freely_reorders():
    a, b, c = _ids(3)
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    # Any permutation of the full set is allowed.
    validate_reorder([a, b, c], statuses, [c, a, b])
    validate_reorder([a, b, c], statuses, [b, c, a])


def test_reorder_rejects_missing_chapter():
    a, b, c = _ids(3)
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="exactly the chapters"):
        validate_reorder([a, b, c], statuses, [a, b])


def test_reorder_rejects_extra_chapter():
    a, b, c = _ids(3)
    d = uuid4()
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="exactly the chapters"):
        validate_reorder([a, b, c], statuses, [a, b, c, d])


def test_reorder_rejects_duplicates():
    a, b, c = _ids(3)
    statuses = {a: STATUS_YET_TO_START, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="duplicate"):
        validate_reorder([a, b, c], statuses, [a, b, b])


def test_reorder_started_chapter_must_stay_at_front():
    # a is in_progress (started) and leads; moving it back is rejected (D-6).
    a, b, c = _ids(3)
    statuses = {a: STATUS_IN_PROGRESS, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="locked"):
        validate_reorder([a, b, c], statuses, [b, a, c])


def test_reorder_upcoming_after_started_reorders_freely():
    # a started and stays first; b and c (upcoming) may swap behind it.
    a, b, c = _ids(3)
    statuses = {a: STATUS_IN_PROGRESS, b: STATUS_YET_TO_START, c: STATUS_YET_TO_START}
    validate_reorder([a, b, c], statuses, [a, c, b])


def test_reorder_keeps_relative_order_of_multiple_started():
    # a (done) then b (in_progress) lead and must keep that relative order;
    # c is upcoming. Submitting them in the same leading order is fine.
    a, b, c = _ids(3)
    statuses = {a: STATUS_DONE, b: STATUS_IN_PROGRESS, c: STATUS_YET_TO_START}
    validate_reorder([a, b, c], statuses, [a, b, c])


def test_reorder_rejects_reordering_two_started_chapters():
    # Swapping the two locked chapters' relative order is rejected.
    a, b, c = _ids(3)
    statuses = {a: STATUS_DONE, b: STATUS_IN_PROGRESS, c: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="locked"):
        validate_reorder([a, b, c], statuses, [b, a, c])


def test_reorder_done_chapter_locked_at_front():
    a, b = _ids(2)
    statuses = {a: STATUS_DONE, b: STATUS_YET_TO_START}
    with pytest.raises(ValueError, match="locked"):
        validate_reorder([a, b], statuses, [b, a])


def test_reorder_single_chapter_noop():
    (a,) = _ids(1)
    validate_reorder([a], {a: STATUS_YET_TO_START}, [a])


def test_reorder_empty_path_noop():
    validate_reorder([], {}, [])
