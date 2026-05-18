"""
F3.1 — Async port of Schema's lp_tagging service.

Used in Phase 3 F3.8 to post-process every generated LP: takes the LP's
HTML body plus the list of sub-SLOs that the LP is *expected* to cover
(derived from the slot's topic) and asks the LLM which sub-SLOs are
actually evidenced in the text, plus the pedagogical-tag analysis from
Schema's original prompt.

Public surface:
    - tag_lp(lp_html, sub_slo_candidates, *, llm=None) -> TaggingResult

The prompt is the verbatim Schema prompt at
`dars/breakdown/prompts/lp_tagging_prompt.txt` (key 'lp_tagging' in
prompt_store), with sub-SLO candidates appended to the user message so
the LLM can return a `covered_sub_slo_ids` list alongside the original
pedagogical tags.

Test coverage (test_lp_tagging_service.py):
    - parse strips markdown fences
    - candidate sub-SLOs are injected into the user message
    - happy path returns covered ids + pedagogical tags + raw response
    - LLM returning unknown sub-SLO ids drops them silently
    - invalid JSON raises ValueError
"""
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, TypedDict
from uuid import UUID

from dars.breakdown.llm_client import call_llm as default_call_llm
from dars.breakdown.prompt_store import get_prompt

log = logging.getLogger("breakdown.lp_tagging")


class SubSLOCandidate(TypedDict):
    """A sub-SLO the LP is expected to cover. id is a UUID; code/statement are display."""
    id: UUID
    code: str
    statement: str


@dataclass
class TaggingResult:
    covered_sub_slo_ids: list[UUID] = field(default_factory=list)
    pedagogical_tags: dict = field(default_factory=dict)
    raw_response: dict = field(default_factory=dict)


LLMCallable = Callable[[str, str], Awaitable[str]]


_FENCE_RE = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)


def _strip_fences(raw: str) -> str:
    """Strip ```json ... ``` fences if the model ignored the strict-JSON instruction."""
    text = raw.strip()
    if not text.startswith("```"):
        return text
    text = _FENCE_RE.sub("", text)
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _format_candidates(candidates: list[SubSLOCandidate]) -> str:
    """Render candidate sub-SLOs as a numbered list for the LLM."""
    lines = []
    for c in candidates:
        lines.append(f"- {c['code']}: {c['statement']}")
    return "\n".join(lines)


def _build_user_message(lp_html: str, candidates: list[SubSLOCandidate]) -> str:
    """
    Compose the user message.

    Format:
        <lp html>

        ---
        Candidate Sub-SLOs (return their codes in `covered_sub_slo_codes`
        if the LP demonstrably covers them):
        - <code>: <statement>
        ...
    """
    candidate_block = _format_candidates(candidates)
    return (
        f"{lp_html}\n\n"
        "---\n"
        "Candidate Sub-SLOs (return their codes under "
        "`covered_sub_slo_codes` if the LP demonstrably covers them — "
        "use the same evidence-based standard as the pedagogical tags):\n"
        f"{candidate_block}\n\n"
        "Append `\"covered_sub_slo_codes\": [\"<code1>\", ...]` to your "
        "JSON output."
    )


async def tag_lp(
    lp_html: str,
    sub_slo_candidates: list[SubSLOCandidate],
    *,
    llm: LLMCallable | None = None,
) -> TaggingResult:
    """
    Tag a generated LP with pedagogical tags + which candidate sub-SLOs it covers.

    Args:
        lp_html:            full LP HTML (or plain text)
        sub_slo_candidates: sub-SLOs the LP is *expected* to cover; the LLM
                            picks the subset actually evidenced
        llm:                async callable(system, user) -> str. Override for
                            tests; defaults to the shared anthropic client.

    Returns:
        TaggingResult(covered_sub_slo_ids, pedagogical_tags, raw_response)

    Raises:
        ValueError: LLM returned empty or unparseable JSON
    """
    log.info(
        "tag_lp: entry lp_chars=%d candidate_count=%d",
        len(lp_html), len(sub_slo_candidates),
    )

    system_prompt = get_prompt("lp_tagging")
    user_message = _build_user_message(lp_html, sub_slo_candidates)
    llm_call = llm or default_call_llm

    raw = await llm_call(system_prompt, user_message)
    if not raw or not raw.strip():
        log.error("tag_lp: empty LLM response")
        raise ValueError("LP tagging: empty LLM response")

    cleaned = _strip_fences(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error("tag_lp: invalid JSON response — %s | head=%r", e, cleaned[:200])
        raise ValueError(f"LP tagging: invalid JSON response: {e}") from e

    # Map returned sub-SLO codes back to UUIDs from the candidates list,
    # silently dropping anything the LLM hallucinated.
    code_to_id = {c["code"]: c["id"] for c in sub_slo_candidates}
    returned_codes = parsed.get("covered_sub_slo_codes") or []
    covered_ids: list[UUID] = []
    unknown_codes: list[str] = []
    for code in returned_codes:
        if not isinstance(code, str):
            continue
        if code in code_to_id:
            covered_ids.append(code_to_id[code])
        else:
            unknown_codes.append(code)
    if unknown_codes:
        log.warning(
            "tag_lp: LLM returned %d unknown sub-SLO codes (dropped): %s",
            len(unknown_codes), unknown_codes,
        )

    pedagogical_tags = {
        "lp_id": parsed.get("lp_id"),
        "grade": parsed.get("grade"),
        "subject": parsed.get("subject"),
        "topic": parsed.get("topic"),
        "slo": parsed.get("slo"),
        "bloom": parsed.get("bloom"),
        "century_skills": parsed.get("century_skills") or [],
        "sections": parsed.get("sections") or {},
    }

    log.info(
        "tag_lp: success covered_sub_slos=%d bloom=%s sections=%s",
        len(covered_ids), pedagogical_tags["bloom"],
        list((pedagogical_tags["sections"] or {}).keys()),
    )
    return TaggingResult(
        covered_sub_slo_ids=covered_ids,
        pedagogical_tags=pedagogical_tags,
        raw_response=parsed,
    )
