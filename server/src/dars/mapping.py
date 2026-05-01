"""
Canonical value mapping for curriculum, grade, and subject.

Dars stores subjects as canonical codes: Eng, Maths, Urdu, Science, GK.
UG LP and UG EG also expect these exact codes — no transformation needed
as long as our stored values are canonical.

This module exists to:
1. Normalise any legacy or variant spellings on ingest (API boundary)
2. Be the single place where subject/grade/curriculum validation lives
"""

# Any variant → canonical code
SUBJECT_ALIASES: dict[str, str] = {
    "english": "Eng",
    "eng": "Eng",
    "mathematics": "Maths",
    "math": "Maths",
    "maths": "Maths",
    "urdu": "Urdu",
    "science": "Science",
    "generalknowledge": "GK",
    "gk": "GK",
}

CURRICULUM_ALIASES: dict[str, str] = {
    "ict": "ICT",
    "punjab": "Punjab",
    "sindh": "Sindh",
}

VALID_GRADES = {1, 2, 3, 4, 5}

CURRICULUM_SUBJECTS: dict[str, list[str]] = {
    "ICT":    ["Eng", "Maths", "Urdu", "Science"],
    "Punjab": ["Eng", "Maths", "Urdu"],
    "Sindh":  ["Eng", "Maths", "Urdu", "Science", "GK"],
}


def canonical_subject(value: str) -> str:
    """Return canonical subject code, raise ValueError if unrecognised."""
    code = SUBJECT_ALIASES.get(value.lower().replace(" ", ""))
    if code is None:
        raise ValueError(f"Unknown subject: {value!r}")
    return code


def canonical_curriculum(value: str) -> str:
    """Return canonical curriculum code, raise ValueError if unrecognised."""
    code = CURRICULUM_ALIASES.get(value.lower())
    if code is None:
        raise ValueError(f"Unknown curriculum: {value!r}")
    return code


def canonical_grade(value: int | str) -> int:
    """Return canonical grade integer, raise ValueError if out of range."""
    g = int(value)
    if g not in VALID_GRADES:
        raise ValueError(f"Grade {g} not in valid range {sorted(VALID_GRADES)}")
    return g


def validate_curriculum_subject(curriculum: str, subject: str) -> None:
    """Raise ValueError if subject is not valid for the given curriculum."""
    allowed = CURRICULUM_SUBJECTS.get(curriculum, [])
    if subject not in allowed:
        raise ValueError(
            f"Subject {subject!r} not valid for curriculum {curriculum!r}. "
            f"Allowed: {allowed}"
        )
