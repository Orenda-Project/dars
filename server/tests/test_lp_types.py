"""F2.4 — lp_type enum unit tests."""
from dars.v2_api.lp_types import (
    LP_TYPES_BY_SUBJECT,
    VALID_SLOT_TYPES,
    is_valid_lp_type,
    valid_lp_types_for_subject,
)


def test_valid_slot_types_matches_migration():
    # Mirror the CHECK in breakdown_slots.slot_type. If this list changes,
    # the migration must be updated too.
    assert VALID_SLOT_TYPES == {
        "lesson",
        "formative_assessment",
        "summative_assessment",
        "revision",
    }


def test_english_and_urdu_share_the_same_lp_set():
    assert LP_TYPES_BY_SUBJECT["Eng"] == LP_TYPES_BY_SUBJECT["Urdu"]


def test_maths_is_distinct():
    assert "concrete" in LP_TYPES_BY_SUBJECT["Maths"]
    assert "reading" not in LP_TYPES_BY_SUBJECT["Maths"]


def test_science_and_gk_only_have_revision():
    assert LP_TYPES_BY_SUBJECT["Science"] == {"revision"}
    assert LP_TYPES_BY_SUBJECT["GK"] == {"revision"}


def test_is_valid_lp_type_allows_null_for_any_subject():
    # Assessment slots may have lp_type=NULL.
    for code in LP_TYPES_BY_SUBJECT:
        assert is_valid_lp_type(code, None) is True


def test_is_valid_lp_type_enforces_subject_specific_set():
    assert is_valid_lp_type("Eng", "reading") is True
    assert is_valid_lp_type("Eng", "concrete") is False
    assert is_valid_lp_type("Maths", "concrete") is True
    assert is_valid_lp_type("Maths", "grammar") is False


def test_unknown_subject_rejects_everything_non_null():
    assert valid_lp_types_for_subject("XYZ") == set()
    assert is_valid_lp_type("XYZ", "reading") is False
    assert is_valid_lp_type("XYZ", None) is True
