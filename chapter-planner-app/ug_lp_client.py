"""
UG_LessonPlan adapter for the Chapter Planning Engine (CPE).

Standalone (D-1): CPE never imports dars/server or UG_LP source — it calls the
UG_LP sync endpoint over HTTP. This module implements the D-7 mapping
(PlanUnit -> UG_LP /api/generate-lp request) and the actual call.

Verified facts (do not re-investigate):
  - sync endpoint:  POST {UG_LP_URL}/api/generate-lp
  - auth header:    api-key: <key>   (NOT Authorization / x-api-key)
  - request body:   { curriculum, grade, subject, lp_type, page_content, class_strength }
                    page_content = unit.topic_text (page_number omitted).
  - 200 response:   { "lesson_plan": "<html>", ...metadata }
"""
from typing import Any, Optional

import httpx

import config
from logging_config import get_logger

logger = get_logger(__name__)

# UG_LP can take ~30-90s; give it generous headroom.
_TIMEOUT_SECONDS = 180.0
_DEFAULT_CLASS_STRENGTH = 30


class UgLpError(RuntimeError):
    """Raised on missing key, non-200, or transport failure calling UG_LP."""


def _unit_get(unit: Any, key: str) -> Any:
    """Read a field from a PlanUnit whether it's a dict or a pydantic model."""
    if isinstance(unit, dict):
        return unit.get(key)
    return getattr(unit, key, None)


def build_lp_request(unit: Any, subject: str, grade: int, curriculum: str) -> dict:
    """D-7 mapping: PlanUnit -> UG_LP /api/generate-lp request body.

    page_content := unit.topic_text (the whole reason units carry topic_text;
    page_number is omitted because page_content takes precedence).
    lp_type     := unit.lp_type
    Other optional UG_LP fields are left unset (defaults off).
    """
    return {
        "curriculum": curriculum,
        "grade": int(grade),
        "subject": subject,
        "lp_type": _unit_get(unit, "lp_type"),
        "page_content": _unit_get(unit, "topic_text") or "",
        "class_strength": _DEFAULT_CLASS_STRENGTH,
    }


async def generate_lp(
    unit: Any,
    subject: str,
    grade: int,
    curriculum: str,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> dict:
    """POST a Plan Unit to UG_LP /api/generate-lp; return the parsed JSON.

    Raises UgLpError on missing key, non-200, or transport error.
    Inject `client` (an httpx.AsyncClient) for tests; otherwise one is created.
    """
    body = build_lp_request(unit, subject, grade, curriculum)
    logger.info(
        "[UG_LP] generate_lp entry — subject=%s grade=%s lp_type=%s content_chars=%d",
        subject, grade, body.get("lp_type"), len(body.get("page_content") or ""),
    )

    if not config.UG_LP_API_KEY:
        logger.error("[UG_LP] no API key configured")
        raise UgLpError("UG_LP API key not configured")

    url = f"{config.UG_LP_URL}/api/generate-lp"
    headers = {"api-key": config.UG_LP_API_KEY}

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
    try:
        try:
            resp = await client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.error("[UG_LP] transport error", exc_info=True)
            raise UgLpError(f"UG_LP request failed: {exc}") from exc

        if resp.status_code != 200:
            detail = (resp.text or "")[:500]
            logger.error("[UG_LP] non-200 — status=%s body=%s", resp.status_code, detail)
            raise UgLpError(f"UG_LP returned {resp.status_code}: {detail}")

        try:
            data = resp.json()
        except ValueError as exc:
            logger.error("[UG_LP] response not JSON", exc_info=True)
            raise UgLpError(f"UG_LP returned non-JSON response: {exc}") from exc
    finally:
        if owns_client:
            await client.aclose()

    lp = data.get("lesson_plan") if isinstance(data, dict) else None
    logger.info(
        "[UG_LP] generate_lp exit — status=200 lesson_plan_chars=%d",
        len(lp or ""),
    )
    return data
