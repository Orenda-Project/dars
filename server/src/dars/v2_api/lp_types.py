"""
F2.4 — `lp_type` enum per subject (D-66 + glossary).

Sourced from LP Assistant's `VALID_LP_TYPES`. The breakdown engine
MUST never emit a value outside this set; LP Assistant silently falls
back to "regular" otherwise (poor output).

Subject codes here match `subjects.code` in the seed:
    Eng / Urdu / Maths / Science / GK
"""

VALID_SLOT_TYPES: set[str] = {
    "lesson",
    "formative_assessment",
    "summative_assessment",
    "revision",
}

LP_TYPES_BY_SUBJECT: dict[str, set[str]] = {
    "Eng": {
        "reading",
        "comprehension_word_meanings",
        "comprehension_qa",
        "grammar",
        "creative_writing",
        "revision",
    },
    "Urdu": {
        "reading",
        "comprehension_word_meanings",
        "comprehension_qa",
        "grammar",
        "creative_writing",
        "revision",
    },
    "Maths": {
        "concrete",
        "pictorial_and_abstract",
        "word_problems",
        "revision",
    },
    "Science": {"revision"},
    "GK": {"revision"},
}


def valid_lp_types_for_subject(subject_code: str) -> set[str]:
    """Return the allowed lp_type set for a subject code, or empty if unknown."""
    return LP_TYPES_BY_SUBJECT.get(subject_code, set())


def is_valid_lp_type(subject_code: str, lp_type: str | None) -> bool:
    """`lp_type` may be NULL for assessment slots; that's allowed."""
    if lp_type is None:
        return True
    return lp_type in valid_lp_types_for_subject(subject_code)
