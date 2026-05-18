"""
F3.11 — pure-Python tests for the batch service helpers we can isolate
from DB. Cache-key composition, default config lookup, etc.
"""
from dars.generated_lps.batch_service import (
    DEFAULT_FA_CONFIG,
    DEFAULT_SA_CONFIG,
    _config_for,
)


def test_default_fa_eng_is_objective_only_ten_questions():
    cfg = DEFAULT_FA_CONFIG["Eng"]
    assert cfg["question_types"] == ["unseen"]
    assert cfg["unseen_categories"] == ["objective"]
    total = sum(cfg["unseen_objective_counts"].values())
    assert total == 10


def test_default_sa_eng_has_objective_plus_subjective():
    cfg = DEFAULT_SA_CONFIG["Eng"]
    assert set(cfg["unseen_categories"]) == {"objective", "subjective"}
    total = (
        sum(cfg["unseen_objective_counts"].values())
        + sum(cfg["unseen_subjective_counts"].values())
    )
    # SA spec says ~20 total; default config is ~18 (12 objective + 6 subjective)
    assert total >= 15


def test_config_for_known_combo():
    assert _config_for("Eng", "formative_assessment") is DEFAULT_FA_CONFIG["Eng"]
    assert _config_for("Eng", "summative_assessment") is DEFAULT_SA_CONFIG["Eng"]


def test_config_for_unknown_combo_returns_none():
    # Maths config not added yet → returns None so the caller skips.
    assert _config_for("Maths", "formative_assessment") is None
    # Unknown slot_type → None
    assert _config_for("Eng", "lesson") is None
