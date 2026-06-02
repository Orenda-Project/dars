"""
Default per-subject assessment configs.

Historically this module also drove batch generation on breakdown publish
(walking breakdown_slots / per-CST slots). That whole path was removed with the
syllabus re-architecture (slots are now teacher-generated; generation no longer
fires on publish — see
docs/features/syllabus-breakdown-and-teacher-chapter-plan/, D-5).

What remains is the default FA/SA config lookup, still used by the generation
router when pre-warming / dispatching exams.
"""
import logging

log = logging.getLogger("generated_lps.batch_service")


# ---------------------------------------------------------------------------
# Default per-subject FA/SA configs (D-46)
# ---------------------------------------------------------------------------


DEFAULT_FA_CONFIG = {
    "Eng": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective"],
        "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
        "unseen_subjective_types": [],
        "unseen_objective_counts": {"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
        "unseen_subjective_counts": {},
    },
}

DEFAULT_SA_CONFIG = {
    "Eng": {
        "question_types": ["unseen"],
        "unseen_categories": ["objective", "subjective"],
        "unseen_objective_types": ["MCQs", "True/False", "Fill in the Blanks"],
        "unseen_subjective_types": ["Brief Answers", "Word Meanings"],
        "unseen_objective_counts": {"MCQs": 6, "True/False": 3, "Fill in the Blanks": 3},
        "unseen_subjective_counts": {"Brief Answers": 4, "Word Meanings": 2},
    },
}


def _config_for(subject_code: str, slot_type: str) -> dict | None:
    """Return the default exam config for a (subject, slot_type) pair, or None
    if we don't know what to send. Unknown combos cause the slot to be skipped
    (logged WARNING), not 500'd."""
    if slot_type == "formative_assessment":
        return DEFAULT_FA_CONFIG.get(subject_code)
    if slot_type == "summative_assessment":
        return DEFAULT_SA_CONFIG.get(subject_code)
    return None
