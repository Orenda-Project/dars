"""
Unit tests for the canonical value mapping module (dars.mapping).

mapping.py is now normalisation-only — it no longer raises on unknown
subjects/grades. DB validation is handled by dars.lookup.service.
"""

from dars.mapping import (
    canonical_curriculum,
    canonical_grade,
    canonical_subject,
)


# ---------------------------------------------------------------------------
# canonical_subject
# ---------------------------------------------------------------------------


def test_canonical_subject_canonical_codes_pass_through():
    assert canonical_subject("Eng") == "Eng"
    assert canonical_subject("Maths") == "Maths"
    assert canonical_subject("Urdu") == "Urdu"
    assert canonical_subject("Science") == "Science"
    assert canonical_subject("GK") == "GK"


def test_canonical_subject_aliases_normalised():
    assert canonical_subject("english") == "Eng"
    assert canonical_subject("English") == "Eng"
    assert canonical_subject("math") == "Maths"
    assert canonical_subject("Math") == "Maths"
    assert canonical_subject("mathematics") == "Maths"
    assert canonical_subject("urdu") == "Urdu"
    assert canonical_subject("science") == "Science"
    assert canonical_subject("gk") == "GK"
    assert canonical_subject("generalknowledge") == "GK"
    assert canonical_subject("Islamiat") == "Islamiat"
    assert canonical_subject("islamiat") == "Islamiat"
    assert canonical_subject("sst") == "SST"
    assert canonical_subject("socialstudies") == "SST"


def test_canonical_subject_unknown_returns_value_as_is():
    # No longer raises — passes through for DB to validate
    assert canonical_subject("physics") == "physics"
    assert canonical_subject("Klingon") == "Klingon"


# ---------------------------------------------------------------------------
# canonical_curriculum
# ---------------------------------------------------------------------------


def test_canonical_curriculum_canonical_codes():
    assert canonical_curriculum("ICT") == "ICT"
    assert canonical_curriculum("Punjab") == "Punjab"
    assert canonical_curriculum("Sindh") == "Sindh"


def test_canonical_curriculum_aliases():
    assert canonical_curriculum("ict") == "ICT"
    assert canonical_curriculum("punjab") == "Punjab"
    assert canonical_curriculum("sindh") == "Sindh"


def test_canonical_curriculum_unknown_raises():
    import pytest
    with pytest.raises(ValueError, match="Unknown curriculum"):
        canonical_curriculum("AKU")


# ---------------------------------------------------------------------------
# canonical_grade
# ---------------------------------------------------------------------------


def test_canonical_grade_valid_integers():
    for g in range(1, 6):
        assert canonical_grade(g) == g


def test_canonical_grade_accepts_strings():
    assert canonical_grade("3") == 3
    assert canonical_grade("5") == 5


def test_canonical_grade_out_of_range_returns_int():
    # No longer raises — passes through for DB to validate
    assert canonical_grade(0) == 0
    assert canonical_grade(99) == 99
