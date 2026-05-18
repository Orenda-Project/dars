"""
F3.3 — tests for the UG_EG v2 client.

Pure-Python: httpx mocked via MockTransport. Verifies:
  - validation (subject enum, generation_type, question_types,
    unseen_categories, non-empty page_content)
  - curriculum mapping (D-61)
  - body construction: only spec'd fields, with conditional sub-fields
    (unseen_objective_*, unseen_subjective_*, long_question_sub_types)
  - api-key header, job_id return
  - non-202 + missing job_id error paths
"""
import json

import httpx
import pytest

from dars.config import settings
from dars.generated_exams.ug_eg_client import (
    UG_EG_PATH,
    ExamRequest,
    request_exam_generation,
)


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setattr(settings, "eg_assistant_url", "https://eg.example.test")
    monkeypatch.setattr(settings, "eg_assistant_api_key", "test-eg-key")


def _fa_payload(**overrides) -> ExamRequest:
    """The FA default config from the reference doc (English G1 ~10 questions)."""
    base = dict(
        curriculum_code="DARS",
        grade=1,
        subject="Eng",
        page_content="Topic OCR text.",
        callback_url="https://dars.example/api/v1/webhooks/exam/j1",
        generation_type="exam",
        question_types=["unseen"],
        unseen_categories=["objective"],
        unseen_objective_types=["MCQs", "True/False", "Fill in the Blanks"],
        unseen_objective_counts={"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2},
    )
    base.update(overrides)
    return ExamRequest(**base)


def _sa_payload() -> ExamRequest:
    """SA default (objective + subjective)."""
    return ExamRequest(
        curriculum_code="DARS",
        grade=1,
        subject="Eng",
        page_content="Two topics joined by newlines.",
        callback_url="https://dars.example/api/v1/webhooks/exam/j2",
        question_types=["unseen"],
        unseen_categories=["objective", "subjective"],
        unseen_objective_types=["MCQs", "True/False", "Fill in the Blanks"],
        unseen_objective_counts={"MCQs": 6, "True/False": 3, "Fill in the Blanks": 3},
        unseen_subjective_types=["Brief Answers", "Word Meanings"],
        unseen_subjective_counts={"Brief Answers": 4, "Word Meanings": 2},
    )


def _mock_transport(handler):
    return httpx.MockTransport(handler)


# ---------------------------------------------------------------------------
# ExamRequest validation
# ---------------------------------------------------------------------------


def test_rejects_unknown_subject():
    with pytest.raises(ValueError, match="not in UG_EG"):
        ExamRequest(
            curriculum_code="DARS", grade=1, subject="Bogus",
            page_content="x", callback_url="https://dars.example/cb",
        )


def test_rejects_unknown_generation_type():
    with pytest.raises(ValueError, match="generation_type"):
        ExamRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="x", callback_url="https://dars.example/cb",
            generation_type="not_a_type",
        )


def test_rejects_unknown_question_type():
    with pytest.raises(ValueError, match="question_types"):
        ExamRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="x", callback_url="https://dars.example/cb",
            question_types=["unseen", "imaginary"],
        )


def test_rejects_empty_question_types():
    with pytest.raises(ValueError, match="non-empty"):
        ExamRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="x", callback_url="https://dars.example/cb",
            question_types=[],
        )


def test_rejects_unknown_unseen_category():
    with pytest.raises(ValueError, match="unseen_categories"):
        ExamRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="x", callback_url="https://dars.example/cb",
            unseen_categories=["objective", "imaginary"],
        )


def test_rejects_missing_page_source():
    with pytest.raises(ValueError, match="page_content or page_ranges"):
        ExamRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="   ", callback_url="https://dars.example/cb",
        )


def test_accepts_page_ranges_alone():
    req = ExamRequest(
        curriculum_code="DARS", grade=1, subject="Eng",
        page_ranges="5-7", callback_url="https://dars.example/cb",
    )
    assert req.page_ranges == "5-7"
    assert req.page_content is None


# ---------------------------------------------------------------------------
# request_exam_generation HTTP behavior
# ---------------------------------------------------------------------------


async def test_fa_body_objective_only():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json={"status": "success", "job_id": "j-fa"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        job_id = await request_exam_generation(_fa_payload(), client=client)

    assert job_id == "j-fa"
    assert captured["url"] == "https://eg.example.test" + UG_EG_PATH
    assert captured["headers"].get("api-key") == "test-eg-key"

    body = captured["body"]
    assert body["curriculum"] == "ICT"
    assert body["grade"] == 1
    assert body["subject"] == "Eng"
    assert body["page_content"] == "Topic OCR text."
    assert body["generation_type"] == "exam"
    assert body["question_types"] == ["unseen"]
    assert body["unseen_categories"] == ["objective"]
    assert body["unseen_objective_types"] == ["MCQs", "True/False", "Fill in the Blanks"]
    assert body["unseen_objective_counts"] == {"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2}
    assert body["include_answer_key"] is True

    # subjective conditional fields must NOT appear when objective-only
    assert "unseen_subjective_types" not in body
    assert "unseen_subjective_counts" not in body
    assert "long_question_sub_types" not in body

    # Forbidden v1 fields
    for forbidden in (
        "custom_system_prompt", "seen_categories",
        "image_generation_enabled", "enable_review",
    ):
        assert forbidden not in body, f"forbidden field leaked: {forbidden}"


async def test_sa_body_includes_subjective_fields():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json={"status": "success", "job_id": "j-sa"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        await request_exam_generation(_sa_payload(), client=client)

    body = captured["body"]
    assert set(body["unseen_categories"]) == {"objective", "subjective"}
    assert body["unseen_subjective_types"] == ["Brief Answers", "Word Meanings"]
    assert body["unseen_subjective_counts"] == {"Brief Answers": 4, "Word Meanings": 2}


async def test_maths_long_question_sub_types_passed_through():
    payload = ExamRequest(
        curriculum_code="DARS", grade=4, subject="Maths",
        page_content="Maths topic", callback_url="https://dars.example/cb",
        question_types=["unseen"], unseen_categories=["subjective"],
        unseen_subjective_types=["Long Question"],
        unseen_subjective_counts={"Long Question": 3},
        long_question_sub_types=["Word Problems", "Graphs & Geometric Problems"],
    )
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json={"status": "success", "job_id": "j-m"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        await request_exam_generation(payload, client=client)

    assert captured["body"]["long_question_sub_types"] == [
        "Word Problems", "Graphs & Geometric Problems"
    ]


async def test_non_202_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"detail": "bad"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await request_exam_generation(_fa_payload(), client=client)


async def test_missing_job_id_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"status": "success"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        with pytest.raises(KeyError, match="job_id"):
            await request_exam_generation(_fa_payload(), client=client)


async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "eg_assistant_api_key", "")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"job_id": "never-fires"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        with pytest.raises(RuntimeError, match="UG_EG_API_KEY"):
            await request_exam_generation(_fa_payload(), client=client)
