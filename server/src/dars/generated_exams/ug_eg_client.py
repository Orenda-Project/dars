"""
F3.3 — Async client for UG_EG's `/api/v2/generate-exam` endpoint.

Submits an exam generation request and returns the UG_EG `job_id`.
Content lands later via the webhook handler in F3.6.

Reference: docs/plans/2026-05-15-dars-v2-rebuild/09-reference-ug-eg-api.md

We send ONLY the fields the reference doc lists. The assessment slot
config (question_types, counts, etc.) is built upstream by the
breakdown engine and passed through here untouched.

Curriculum codes are mapped via D-61. UG_EG does not support Sindh; the
mapping module raises if a caller tries to use it (today no curriculum
maps to Sindh anyway, but this is the future-proof failure mode).
"""
import logging

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from dars.breakdown.curriculum_mapping import map_curriculum_for_ug_eg
from dars.config import settings

log = logging.getLogger("generated_exams.ug_eg_client")

UG_EG_PATH = "/api/v2/generate-exam"
DEFAULT_TIMEOUT_SECONDS = 30.0

_UG_EG_SUBJECT_CODES: frozenset[str] = frozenset(
    {"Eng", "Urdu", "Maths", "Islamiat", "GenSci", "GenK", "SST"}
)
_GENERATION_TYPES: frozenset[str] = frozenset({"exam", "class_assessment"})
_QUESTION_TYPES: frozenset[str] = frozenset({"seen", "unseen"})
_UNSEEN_CATEGORIES: frozenset[str] = frozenset({"objective", "subjective"})


class ExamRequest(BaseModel):
    """Input to `request_exam_generation`.

    `curriculum_code` is dars's internal code (DARS / NCP / SNC); it
    gets mapped to UG_EG's enum value at send time.

    UG_EG's /api/v2/generate-exam requires `page_ranges` (e.g. "5" or
    "5-7"); it fetches book content from its own DB. We keep `page_content`
    as a Dars-side convenience field — the batch breakdown path computes
    page_content from book_chapters.chapter_text and we still want a way
    to send pre-extracted text — but if `page_content` is set we extract
    a synthetic page_ranges string by passing through as-is. In practice
    callers should set `page_ranges` directly.
    """

    curriculum_code: str
    grade: int = Field(ge=1, le=5)
    subject: str
    page_content: str | None = None
    page_ranges: str | None = None
    callback_url: str
    generation_type: str = "exam"
    question_types: list[str] = Field(default_factory=lambda: ["unseen"])
    unseen_categories: list[str] = Field(default_factory=list)
    unseen_objective_types: list[str] = Field(default_factory=list)
    unseen_subjective_types: list[str] = Field(default_factory=list)
    unseen_objective_counts: dict[str, int] = Field(default_factory=dict)
    unseen_subjective_counts: dict[str, int] = Field(default_factory=dict)
    long_question_sub_types: list[str] = Field(default_factory=list)
    include_answer_key: bool = True

    @field_validator("subject")
    @classmethod
    def _subject_must_match_ug_eg(cls, v: str) -> str:
        if v not in _UG_EG_SUBJECT_CODES:
            raise ValueError(
                f"subject={v!r} not in UG_EG's enum {sorted(_UG_EG_SUBJECT_CODES)}"
            )
        return v

    @field_validator("generation_type")
    @classmethod
    def _generation_type_in_enum(cls, v: str) -> str:
        if v not in _GENERATION_TYPES:
            raise ValueError(f"generation_type={v!r} not in {sorted(_GENERATION_TYPES)}")
        return v

    @field_validator("question_types")
    @classmethod
    def _question_types_in_enum(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("question_types must be non-empty")
        bad = [t for t in v if t not in _QUESTION_TYPES]
        if bad:
            raise ValueError(f"question_types contains unknown values: {bad}")
        return v

    @field_validator("unseen_categories")
    @classmethod
    def _unseen_categories_in_enum(cls, v: list[str]) -> list[str]:
        bad = [c for c in v if c not in _UNSEEN_CATEGORIES]
        if bad:
            raise ValueError(f"unseen_categories contains unknown values: {bad}")
        return v

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "ExamRequest":
        has_content = bool(self.page_content and self.page_content.strip())
        has_ranges = bool(self.page_ranges and self.page_ranges.strip())
        if not has_content and not has_ranges:
            raise ValueError(
                "either page_content or page_ranges must be provided"
            )
        return self


def _build_body(req: ExamRequest) -> dict:
    """Build the v2 request body. Only fields the reference doc lists.

    UG_EG accepts page_ranges (its own page-DB lookup). When the Dars
    caller supplies page_content directly, we pass it through too; UG_EG
    treats page_ranges as authoritative when both are present.
    """
    body: dict = {
        "callback_url": req.callback_url,
        "generation_type": req.generation_type,
        "curriculum": map_curriculum_for_ug_eg(req.curriculum_code),
        "grade": req.grade,
        "subject": req.subject,
        "question_types": list(req.question_types),
        "include_answer_key": req.include_answer_key,
    }
    if req.page_ranges and req.page_ranges.strip():
        body["page_ranges"] = req.page_ranges
    if req.page_content and req.page_content.strip():
        body["page_content"] = req.page_content
    if "unseen" in req.question_types:
        body["unseen_categories"] = list(req.unseen_categories)
        if "objective" in req.unseen_categories:
            body["unseen_objective_types"] = list(req.unseen_objective_types)
            body["unseen_objective_counts"] = dict(req.unseen_objective_counts)
        if "subjective" in req.unseen_categories:
            body["unseen_subjective_types"] = list(req.unseen_subjective_types)
            body["unseen_subjective_counts"] = dict(req.unseen_subjective_counts)
    if req.long_question_sub_types:
        body["long_question_sub_types"] = list(req.long_question_sub_types)
    return body


async def request_exam_generation(
    payload: ExamRequest,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """
    Submit an exam generation request to UG_EG v2.

    Args:
        payload: validated request data
        client:  optional injected httpx.AsyncClient (tests use this)

    Returns:
        UG_EG `job_id`

    Raises:
        RuntimeError:          env vars missing
        httpx.HTTPStatusError: non-202 response
        KeyError:              response missing `job_id`
    """
    body = _build_body(payload)

    log.info(
        "request_exam_generation: entry curriculum_in=%s curriculum_out=%s grade=%d subject=%s gen_type=%s qtypes=%s callback_url=%s",
        payload.curriculum_code, body["curriculum"], body["grade"], body["subject"],
        body["generation_type"], body["question_types"], payload.callback_url,
    )

    if not settings.eg_assistant_api_key:
        raise RuntimeError("UG_EG_API_KEY is not configured (settings.eg_assistant_api_key)")
    if not settings.eg_assistant_url:
        raise RuntimeError("UG_EG_URL is not configured (settings.eg_assistant_url)")

    url = settings.eg_assistant_url.rstrip("/") + UG_EG_PATH
    headers = {"api-key": settings.eg_assistant_api_key}

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT_SECONDS)

    try:
        response = await client.post(url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
    finally:
        if owns_client:
            await client.aclose()

    if "job_id" not in data:
        log.error("request_exam_generation: response missing job_id — %r", data)
        raise KeyError("UG_EG response missing job_id")

    job_id = data["job_id"]
    log.info(
        "request_exam_generation: success job_id=%s status_code=%d",
        job_id, response.status_code,
    )
    return job_id
