"""core-book-import F-1.2 — the breakdown prompt is vendored in-package (D-4).

No workstation path; loads on a clean checkout.
"""
from dars.v2_api import book_import_service as svc
from dars.v2_api.lp_type_classifier import VALID_LP_TYPES


def test_breakdown_prompt_loads_from_package():
    text = svc._load_breakdown_prompt()
    assert isinstance(text, str) and len(text) > 100
    assert "/home/" not in text  # not a workstation path leak
    assert "sub-SLO" in text.lower() or "sub slo" in text.lower()


def test_valid_lp_types_are_the_five_enum_values():
    assert VALID_LP_TYPES == frozenset({
        "reading", "comprehension_word_meanings", "comprehension_qa",
        "grammar", "creative_writing",
    })
