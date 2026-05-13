"""
Normalisation helpers for grade and subject values.

These functions normalise shape only (whitespace, case, int cast).
Validation against the DB happens in dars.lookup.service.
"""

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
    "islamiat": "Islamiat",
    "sst": "SST",
    "socialstudies": "SST",
}

CURRICULUM_ALIASES: dict[str, str] = {
    "ict": "ICT",
    "punjab": "Punjab",
    "sindh": "Sindh",
}


def canonical_subject(value: str) -> str:
    """Normalise subject to canonical code. Returns value as-is if no alias found (DB will validate)."""
    return SUBJECT_ALIASES.get(value.lower().replace(" ", ""), value)


def canonical_curriculum(value: str) -> str:
    """Return canonical curriculum code, raise ValueError if unrecognised."""
    code = CURRICULUM_ALIASES.get(value.lower())
    if code is None:
        raise ValueError(f"Unknown curriculum: {value!r}")
    return code


def canonical_grade(value: int | str) -> int:
    """Cast to int. DB will validate if it's a known grade."""
    return int(value)
