"""
F3.2 — tests for the LP Assistant v3 client.

Pure-Python: httpx is mocked via httpx.MockTransport so no real HTTP
fires. The client must:
  - validate inputs (subject enum, lp_type per subject, non-empty page_content)
  - map curriculum_code via D-61
  - send ONLY the v3 fields (no `topic`, `custom_prompt`, etc.)
  - send `api-key` header
  - return job_id from the 202 response
  - raise on non-202 / missing job_id
"""
import json

import httpx
import pytest

from dars.config import settings
from dars.generated_lps.lp_assistant_client import (
    LP_ASSISTANT_PATH,
    LPRequest,
    request_lp_generation,
)


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    monkeypatch.setattr(settings, "lp_assistant_url", "https://lp.example.test")
    monkeypatch.setattr(settings, "lp_assistant_api_key", "test-lp-key")


def _good_payload(**overrides) -> LPRequest:
    base = dict(
        curriculum_code="DARS",
        grade=1,
        subject="Eng",
        page_content="Hello world.",
        lp_type="reading",
        callback_url="https://dars.example.test/api/v1/webhooks/lp/abc",
    )
    base.update(overrides)
    return LPRequest(**base)


# ---------------------------------------------------------------------------
# LPRequest validation
# ---------------------------------------------------------------------------


def test_lp_request_rejects_unknown_subject():
    with pytest.raises(ValueError, match="not in LP Assistant"):
        LPRequest(
            curriculum_code="DARS", grade=1, subject="NotASubject",
            page_content="x", lp_type="reading",
            callback_url="https://dars.example/cb",
        )


def test_lp_request_rejects_invalid_lp_type_for_subject():
    with pytest.raises(ValueError, match="invalid for subject"):
        LPRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="x", lp_type="concrete",  # Maths-only
            callback_url="https://dars.example/cb",
        )


def test_lp_request_rejects_both_page_sources_missing():
    with pytest.raises(ValueError, match="page_content or page_number"):
        LPRequest(
            curriculum_code="DARS", grade=1, subject="Eng",
            page_content="   ", lp_type="reading",
            callback_url="https://dars.example/cb",
        )


def test_lp_request_accepts_page_number_alone():
    req = LPRequest(
        curriculum_code="DARS", grade=1, subject="Eng",
        page_number="5", lp_type="reading",
        callback_url="https://dars.example/cb",
    )
    assert req.page_number == "5"
    assert req.page_content is None


def test_lp_request_grade_bounds():
    with pytest.raises(ValueError):
        LPRequest(
            curriculum_code="DARS", grade=6, subject="Eng",
            page_content="x", lp_type="reading",
            callback_url="https://dars.example/cb",
        )


# ---------------------------------------------------------------------------
# request_lp_generation HTTP behavior
# ---------------------------------------------------------------------------


def _mock_transport(handler):
    return httpx.MockTransport(handler)


async def test_sends_only_v3_fields_and_returns_job_id():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json={"job_id": "j-123"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        job_id = await request_lp_generation(_good_payload(), client=client)

    assert job_id == "j-123"
    assert captured["url"] == "https://lp.example.test" + LP_ASSISTANT_PATH
    assert captured["headers"].get("api-key") == "test-lp-key"

    # Curriculum mapped DARS -> ICT
    assert captured["body"]["curriculum"] == "ICT"
    assert captured["body"]["grade"] == 1
    assert captured["body"]["subject"] == "Eng"
    assert captured["body"]["page_content"] == "Hello world."
    assert captured["body"]["lp_type"] == "reading"
    assert captured["body"]["class_strength"] == 30
    assert captured["body"]["generate_bilingual"] is False
    assert captured["body"]["callback_url"].endswith("/abc")

    # Forbidden v1/v2 fields must NOT appear. page_number is no longer
    # forbidden — the quick-LP path uses it; but this test sets
    # page_content so page_number should still be absent here.
    for forbidden in (
        "topic", "custom_prompt", "system_prompt",
        "exercise_page_number",
        "enable_review", "revision_lp", "is_objective", "is_subjective",
        "image_generation_enabled", "feedback", "selected_model", "sub_region",
    ):
        assert forbidden not in captured["body"], f"forbidden field leaked: {forbidden}"
    assert "page_number" not in captured["body"], "page_content path should not also send page_number"


async def test_curriculum_snc_maps_to_punjab():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(202, json={"job_id": "j-snc"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        await request_lp_generation(
            _good_payload(curriculum_code="SNC"), client=client
        )

    assert captured["body"]["curriculum"] == "Punjab"


async def test_non_202_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"detail": "boom"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await request_lp_generation(_good_payload(), client=client)


async def test_missing_job_id_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"not_job_id": "huh"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        with pytest.raises(KeyError, match="job_id"):
            await request_lp_generation(_good_payload(), client=client)


async def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "lp_assistant_api_key", "")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(202, json={"job_id": "never-fires"})

    async with httpx.AsyncClient(transport=_mock_transport(handler)) as client:
        with pytest.raises(RuntimeError, match="LP_ASSISTANT_API_KEY"):
            await request_lp_generation(_good_payload(), client=client)
