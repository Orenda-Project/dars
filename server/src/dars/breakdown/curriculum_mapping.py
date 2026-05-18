"""
D-61 — Map dars's `curriculums.code` to the curriculum enums used by
LP Assistant and UG_EG.

Shared by F3.2 (LP Assistant client) and F3.3 (UG_EG client) so a new
curriculum + Shujaan-side support is a one-line edit here.

Coverage today (from the reference docs):
    LP Assistant accepts: ICT | Punjab | Sindh
    UG_EG accepts:        ICT | Punjab          (Sindh unsupported)

Per D-61: DARS -> ICT, NCP -> ICT, SNC -> Punjab. Unknown codes fail
fast — never silently default. If UG_EG can't handle a curriculum,
fail fast too (caller must validate before calling the client).
"""

CURRICULUM_TO_LP_ASSISTANT: dict[str, str] = {
    "DARS": "ICT",
    "NCP": "ICT",
    "SNC": "Punjab",
}

CURRICULUM_TO_UG_EG: dict[str, str] = {
    "DARS": "ICT",
    "NCP": "ICT",
    "SNC": "Punjab",
}


class UnknownCurriculumError(ValueError):
    """Raised when a curriculum code has no Shujaan-side mapping."""


def map_curriculum_for_lp_assistant(curriculum_code: str) -> str:
    """Return LP Assistant's curriculum enum value, or raise."""
    if curriculum_code not in CURRICULUM_TO_LP_ASSISTANT:
        raise UnknownCurriculumError(
            f"no LP Assistant mapping for curriculum code {curriculum_code!r}; "
            f"known: {sorted(CURRICULUM_TO_LP_ASSISTANT)}"
        )
    return CURRICULUM_TO_LP_ASSISTANT[curriculum_code]


def map_curriculum_for_ug_eg(curriculum_code: str) -> str:
    """Return UG_EG's curriculum enum value, or raise."""
    if curriculum_code not in CURRICULUM_TO_UG_EG:
        raise UnknownCurriculumError(
            f"no UG_EG mapping for curriculum code {curriculum_code!r}; "
            f"known: {sorted(CURRICULUM_TO_UG_EG)}"
        )
    return CURRICULUM_TO_UG_EG[curriculum_code]
