"""
Configuration and constants for the Chapter Planning Engine (CPE).

CPE is a standalone FastAPI service (D-1). It is NOT imported by the dars backend.
"""
import os
from dotenv import load_dotenv
from logging_config import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv()

# ============================================================================
# Application Configuration
# ============================================================================
ENVIRONMENT = os.getenv("ENVIRONMENT", "stage").lower()  # stage or prod

# ============================================================================
# Valid lp_type values per subject (D-5)
# Copied VERBATIM from UG_LessonPlan/config.py::VALID_LP_TYPES as of 2026-06-03
# (see docs/features/chapter-planner-engine/06-reference-ug-lp-input.md).
# The LLM picks lp_type only from the list for the request's subject.
# ============================================================================
VALID_LP_TYPES = {
    "Eng":      ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Urdu":     ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Maths":    ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
    "Science":  ["revision"],
    "GK":       ["revision"],
    "Islamiat": ["revision"],
    "SST":      ["revision"],
}

# Valid subjects = keys of VALID_LP_TYPES
VALID_SUBJECTS = list(VALID_LP_TYPES.keys())

# Log configuration on startup
logger.info(f"[CONFIG] Environment: {ENVIRONMENT}")
logger.info(f"[CONFIG] Subjects: {VALID_SUBJECTS}")
