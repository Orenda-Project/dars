"""
F3.2+F3.3 — tests for the shared curriculum mapping (D-61).
"""
import pytest

from dars.breakdown.curriculum_mapping import (
    UnknownCurriculumError,
    map_curriculum_for_lp_assistant,
    map_curriculum_for_ug_eg,
)


def test_lp_assistant_dars_to_ict():
    assert map_curriculum_for_lp_assistant("DARS") == "ICT"


def test_lp_assistant_ncp_to_ict():
    assert map_curriculum_for_lp_assistant("NCP") == "ICT"


def test_lp_assistant_snc_to_punjab():
    assert map_curriculum_for_lp_assistant("SNC") == "Punjab"


def test_lp_assistant_unknown_raises():
    with pytest.raises(UnknownCurriculumError):
        map_curriculum_for_lp_assistant("FOO")


def test_ug_eg_mapping_matches_lp_assistant_today():
    """Both clients support the same codes today; if this diverges, change both maps deliberately."""
    assert map_curriculum_for_ug_eg("DARS") == "ICT"
    assert map_curriculum_for_ug_eg("NCP") == "ICT"
    assert map_curriculum_for_ug_eg("SNC") == "Punjab"


def test_ug_eg_unknown_raises():
    with pytest.raises(UnknownCurriculumError):
        map_curriculum_for_ug_eg("XYZ")
