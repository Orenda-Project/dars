"""F2.13 — pure-Python guards on onboard_cst (input validation)."""
import pytest

from dars.breakdown.onboarding_service import onboard_cst


class _FakeConn:
    """Tiny stub: we never reach the DB because the input check fires first."""

    async def fetchrow(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("DB should not be touched on input-validation failure")

    async def execute(self, *args, **kwargs):  # pragma: no cover
        raise AssertionError("DB should not be touched on input-validation failure")


async def test_onboard_rejects_non_positive_inputs():
    fake_conn = _FakeConn()
    fake_cst = "00000000-0000-0000-0000-000000000000"
    with pytest.raises(ValueError):
        await onboard_cst(fake_conn, cst_id=fake_cst, chapter_position=0, chapter_day=1)
    with pytest.raises(ValueError):
        await onboard_cst(fake_conn, cst_id=fake_cst, chapter_position=1, chapter_day=0)
    with pytest.raises(ValueError):
        await onboard_cst(fake_conn, cst_id=fake_cst, chapter_position=-3, chapter_day=2)
