"""
F-3.1 — tests for the per-subject Default FA Config + safe lookup.

Pure (no DB): assert the config shape is valid as ExamRequest kwargs, that a
known subject and the generic fallback both produce a constructible
ExamRequest.question_config, and that an unknown subject returns the generic
default without raising.
"""
from dars.generated_exams.service import (
    DEFAULT_FA_CONFIG,
    GENERATION_TYPE_FA,
    _GENERIC_FA_CONFIG,
    build_question_config,
    default_fa_config,
)
from dars.generated_exams.ug_eg_client import ExamRequest


def _request_from_config(subject: str, config: dict) -> ExamRequest:
    return ExamRequest(
        curriculum_code="DARS",
        grade=1,
        subject=subject,
        page_content="x",
        callback_url="https://dars.example/cb",
        generation_type=GENERATION_TYPE_FA,
        **config,
    )


def test_generation_type_fa_is_valid_exam_request_enum():
    # D-10 named 'formative', but ExamRequest only accepts the UG_EG enum;
    # the FA maps to 'class_assessment'. This must construct, not raise.
    req = _request_from_config("Eng", default_fa_config("Eng"))
    assert req.generation_type == "class_assessment"
    assert GENERATION_TYPE_FA == "class_assessment"


def test_default_fa_eng_is_short_objective_quiz():
    cfg = DEFAULT_FA_CONFIG["Eng"]
    assert cfg["question_types"] == ["unseen"]
    assert cfg["unseen_categories"] == ["objective"]
    total = sum(cfg["unseen_objective_counts"].values())
    # Formative != summative — modest count.
    assert total <= 12
    assert total == 10


def test_default_fa_eng_builds_valid_exam_request():
    req = _request_from_config("Eng", default_fa_config("Eng"))
    cfg = build_question_config(req)
    assert cfg["subject"] == "Eng"
    assert cfg["generation_type"] == "class_assessment"
    assert cfg["unseen_objective_counts"]["MCQs"] == 5
    assert "page_content" not in cfg


def test_unknown_subject_returns_generic_default_no_raise():
    # SST has no specific entry → generic default, never raises.
    cfg = default_fa_config("SST")
    assert cfg == _GENERIC_FA_CONFIG
    # And it produces a constructible ExamRequest for a valid UG_EG subject.
    req = _request_from_config("SST", cfg)
    assert req.subject == "SST"
    assert req.question_types == ["unseen"]


def test_default_fa_config_returns_fresh_copy():
    # Mutating the returned dict must not corrupt the module-level config.
    cfg = default_fa_config("Eng")
    cfg["unseen_objective_counts"]["MCQs"] = 999
    assert DEFAULT_FA_CONFIG["Eng"]["unseen_objective_counts"]["MCQs"] == 5


def test_known_subjects_each_build_valid_request():
    for subject in DEFAULT_FA_CONFIG:
        req = _request_from_config(subject, default_fa_config(subject))
        assert req.subject == subject
        # No subjective questions in a formative default (objective-only).
        assert "subjective" not in req.unseen_categories
