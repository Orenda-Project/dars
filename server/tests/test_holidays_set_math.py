"""F2.10 — pure set-math tests for apply_overrides."""
from datetime import date

from dars.breakdown.holidays import apply_overrides


def _ov(d: date, action: str) -> dict:
    return {"date": d, "action": action}


def test_apply_overrides_add():
    base = {date(2026, 5, 1)}
    out = apply_overrides(base, [_ov(date(2026, 5, 2), "add")])
    assert out == {date(2026, 5, 1), date(2026, 5, 2)}


def test_apply_overrides_remove():
    base = {date(2026, 5, 1), date(2026, 5, 2)}
    out = apply_overrides(base, [_ov(date(2026, 5, 1), "remove")])
    assert out == {date(2026, 5, 2)}


def test_apply_overrides_remove_missing_is_noop():
    base = {date(2026, 5, 1)}
    out = apply_overrides(base, [_ov(date(2026, 12, 25), "remove")])
    assert out == {date(2026, 5, 1)}


def test_apply_overrides_unknown_action_ignored():
    base = {date(2026, 5, 1)}
    out = apply_overrides(base, [_ov(date(2026, 5, 2), "flarp")])
    assert out == base


def test_apply_overrides_three_level_example_from_spec():
    """Org has 3 holidays; school removes 1; CST adds 2 personal → effective = 4."""
    org_holidays = {date(2026, 5, 1), date(2026, 5, 2), date(2026, 5, 3)}
    after_school = apply_overrides(org_holidays, [_ov(date(2026, 5, 2), "remove")])
    after_cst = apply_overrides(after_school, [
        _ov(date(2026, 6, 1), "add"),
        _ov(date(2026, 6, 2), "add"),
    ])
    assert len(after_cst) == 4
    assert date(2026, 5, 2) not in after_cst
    assert {date(2026, 6, 1), date(2026, 6, 2)} <= after_cst
