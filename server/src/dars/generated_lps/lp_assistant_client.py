"""
F3.2 — Async client for LP Assistant's `/api/v3/generate-lp` endpoint.

Replaces the legacy v1 sync call. Submits an LP generation request and
returns the LP Assistant `job_id`. The actual content lands later via
the webhook handler in F3.6.

Reference: docs/plans/2026-05-15-dars-v2-rebuild/08-reference-lp-assistant-api.md

We send the fields the reference doc lists, plus `custom_prompt` when the
caller provides sub-SLO statements to steer the LLM (D-1 in
docs/features/lp-slo-injection-and-linkage/01-decision-log.md, which
supersedes the v2 rebuild plan's "Do NOT send custom_prompt" line in F3.2).
Other fields (`topic`, `system_prompt`, `page_number`,
`exercise_page_number`) remain intentionally omitted — sending them would
either change LP Assistant's behavior in ways v1 doesn't want or trigger
the "regular" lp_type fallback.

Subject codes are passed through unchanged; they already match LP
Assistant's enum after the F1.2 lookups seed (`Eng`, `Urdu`, `Maths`,
`Science`, `GK`). Curriculum codes are mapped via D-61.
"""
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, Field, field_validator, model_validator

from dars.breakdown.curriculum_mapping import map_curriculum_for_lp_assistant
from dars.config import settings
from dars.v2_api.lp_types import is_valid_lp_type

log = logging.getLogger("generated_lps.lp_assistant_client")

LP_ASSISTANT_PATH = "/api/v3/generate-lp"
DEFAULT_TIMEOUT_SECONDS = 30.0  # LP Assistant returns 202 immediately

_SUBJECT_CODES: frozenset[str] = frozenset({"Eng", "Urdu", "Maths", "Science", "GK"})


class LPRequest(BaseModel):
    """Input to `request_lp_generation`.

    `curriculum_code` is dars's internal code (DARS / NCP / SNC); it gets
    mapped to LP Assistant's enum value at send time.

    Either `page_content` (raw text already extracted) OR `page_number`
    (string like "5" or "5-7"; LP Assistant fetches from its own book DB)
    must be provided. The batch breakdown path passes `page_content`; the
    quick endpoint passes `page_number`.
    """

    curriculum_code: str
    grade: int = Field(ge=1, le=5)
    subject: str  # must match LP Assistant's enum (Eng/Urdu/Maths/Science/GK)
    page_content: str | None = None
    page_number: str | None = None
    lp_type: str
    callback_url: str
    class_strength: int = 30
    generate_bilingual: bool = False
    # D-1: sub-SLO statements the LP should cover. If empty/None we omit
    # `custom_prompt` entirely (D-4 — empty topics dispatch cleanly).
    sub_slo_statements: list[str] | None = None

    @field_validator("subject")
    @classmethod
    def _subject_must_match_lp_assistant(cls, v: str) -> str:
        if v not in _SUBJECT_CODES:
            raise ValueError(
                f"subject={v!r} not in LP Assistant's enum {sorted(_SUBJECT_CODES)}"
            )
        return v

    @field_validator("lp_type")
    @classmethod
    def _lp_type_must_be_valid_for_subject(cls, v: str, info) -> str:
        subject = info.data.get("subject")
        if subject and not is_valid_lp_type(subject, v):
            raise ValueError(
                f"lp_type={v!r} is invalid for subject={subject}; "
                "LP Assistant would silently fall back to 'regular'"
            )
        return v

    @model_validator(mode="after")
    def _exactly_one_source(self) -> "LPRequest":
        has_content = bool(self.page_content and self.page_content.strip())
        has_number = bool(self.page_number and self.page_number.strip())
        if not has_content and not has_number:
            raise ValueError(
                "either page_content or page_number must be provided"
            )
        return self


def _build_custom_prompt(statements: list[str]) -> str:
    """Format the D-1 sub-SLO coverage instruction. Frozen string."""
    bullets = "\n".join(f"- {s}" for s in statements)
    return (
        "After this lesson plan, the following sub-SLOs should be covered:\n"
        f"{bullets}"
    )


def _build_body(req: LPRequest) -> dict:
    """Build the v3 request body — fields the reference doc lists plus an
    optional `custom_prompt` for sub-SLO steering (D-1)."""
    body: dict = {
        "curriculum": map_curriculum_for_lp_assistant(req.curriculum_code),
        "grade": req.grade,
        "subject": req.subject,
        "lp_type": req.lp_type,
        "class_strength": req.class_strength,
        "generate_bilingual": req.generate_bilingual,
        "callback_url": req.callback_url,
    }
    if req.page_content and req.page_content.strip():
        body["page_content"] = req.page_content
    elif req.page_number and req.page_number.strip():
        body["page_number"] = req.page_number
    if req.sub_slo_statements:
        body["custom_prompt"] = _build_custom_prompt(req.sub_slo_statements)
    return body


async def request_lp_generation(
    payload: LPRequest,
    *,
    client: httpx.AsyncClient | None = None,
) -> str:
    """
    Submit an LP generation request to LP Assistant v3.

    Args:
        payload: validated request data
        client:  optional injected httpx.AsyncClient (tests use this)

    Returns:
        LP Assistant `job_id` (UUID string)

    Raises:
        RuntimeError:        env vars missing
        httpx.HTTPStatusError: non-202 response
        KeyError:            response missing `job_id`
    """
    body = _build_body(payload)

    sub_slo_count = len(payload.sub_slo_statements or [])
    log.info(
        "request_lp_generation: entry curriculum_in=%s curriculum_out=%s grade=%d subject=%s lp_type=%s callback_url=%s sub_slo_count=%d",
        payload.curriculum_code, body["curriculum"], body["grade"],
        body["subject"], body["lp_type"], payload.callback_url, sub_slo_count,
    )

    if not settings.lp_assistant_api_key:
        raise RuntimeError("LP_ASSISTANT_API_KEY is not configured")
    if not settings.lp_assistant_url:
        raise RuntimeError("LP_ASSISTANT_URL is not configured")

    url = settings.lp_assistant_url.rstrip("/") + LP_ASSISTANT_PATH
    headers = {"api-key": settings.lp_assistant_api_key}

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
        log.error("request_lp_generation: response missing job_id — %r", data)
        raise KeyError("LP Assistant response missing job_id")

    job_id = data["job_id"]
    log.info(
        "request_lp_generation: success job_id=%s status_code=%d",
        job_id, response.status_code,
    )
    return job_id
