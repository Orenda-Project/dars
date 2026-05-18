"""
F3.1 — tests for the async LP tagging service.

Pure-Python: no DB, no real LLM. The service accepts an injectable async
LLM callable so all cases are covered with a fake.
"""
import json
from uuid import uuid4

import pytest

from dars.breakdown.lp_tagging_service import (
    SubSLOCandidate,
    TaggingResult,
    _strip_fences,
    tag_lp,
)


def _candidate(code: str, statement: str) -> SubSLOCandidate:
    return {"id": uuid4(), "code": code, "statement": statement}


def _valid_response(covered_codes: list[str]) -> dict:
    return {
        "lp_id": None,
        "grade": "1",
        "subject": "English",
        "topic": "Alphabet recognition",
        "slo": "R1-01",
        "bloom": "Remember",
        "century_skills": [{"skill": "Communication", "section": "practice"}],
        "sections": {
            "hook": {"tags": ["Visual", "Prior Knowledge"]},
            "explanation": {"tags": ["I-Do-Model", "I-Do-Visual"]},
            "practice": {"tags": ["You-Do-Independent"]},
            "conclusion": {"tags": ["Wrap-Summary"]},
        },
        "covered_sub_slo_codes": covered_codes,
    }


# ---------------------------------------------------------------------------
# Fence stripping
# ---------------------------------------------------------------------------


def test_strip_fences_plain_json():
    assert _strip_fences('{"a": 1}') == '{"a": 1}'


def test_strip_fences_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert _strip_fences(raw) == '{"a": 1}'


def test_strip_fences_bare_fence():
    raw = '```\n{"a": 1}\n```'
    assert _strip_fences(raw) == '{"a": 1}'


def test_strip_fences_with_whitespace():
    raw = '   ```json\n  {"a": 1}\n```  '
    assert _strip_fences(raw) == '{"a": 1}'


# ---------------------------------------------------------------------------
# tag_lp happy path
# ---------------------------------------------------------------------------


async def test_tag_lp_returns_covered_ids_and_pedagogical_tags():
    cand_a = _candidate("R1-01.1", "Identify all 26 letters of the English alphabet.")
    cand_b = _candidate("R1-01.2", "Name all 26 letters of the English alphabet.")
    candidates = [cand_a, cand_b]

    captured: dict = {}

    async def fake_llm(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return json.dumps(_valid_response(["R1-01.1", "R1-01.2"]))

    result = await tag_lp("<h1>Letters</h1>", candidates, llm=fake_llm)

    assert isinstance(result, TaggingResult)
    assert set(result.covered_sub_slo_ids) == {cand_a["id"], cand_b["id"]}
    assert result.pedagogical_tags["bloom"] == "Remember"
    assert result.pedagogical_tags["sections"]["hook"]["tags"] == [
        "Visual",
        "Prior Knowledge",
    ]
    assert result.raw_response["covered_sub_slo_codes"] == ["R1-01.1", "R1-01.2"]

    # The user message carries the LP body + candidate list so the LLM
    # has both inputs.
    assert "<h1>Letters</h1>" in captured["user"]
    assert "R1-01.1: Identify all 26 letters" in captured["user"]
    assert "R1-01.2: Name all 26 letters" in captured["user"]
    # System prompt is loaded from the prompt store; sanity-check it's
    # the Schema lp_tagging prompt by looking for one of its anchors.
    assert "evidence" in captured["system"].lower()


async def test_tag_lp_partial_coverage():
    cand_a = _candidate("R1-01.1", "Identify letters.")
    cand_b = _candidate("R1-01.2", "Name letters.")

    async def fake_llm(system: str, user: str) -> str:
        return json.dumps(_valid_response(["R1-01.1"]))

    result = await tag_lp("<p>lp</p>", [cand_a, cand_b], llm=fake_llm)
    assert result.covered_sub_slo_ids == [cand_a["id"]]


async def test_tag_lp_no_candidates_covered():
    cand = _candidate("R1-01.1", "Identify letters.")

    async def fake_llm(system: str, user: str) -> str:
        return json.dumps(_valid_response([]))

    result = await tag_lp("<p>lp</p>", [cand], llm=fake_llm)
    assert result.covered_sub_slo_ids == []
    assert result.pedagogical_tags["bloom"] == "Remember"


# ---------------------------------------------------------------------------
# Robustness: fenced output + hallucinated codes + bad JSON
# ---------------------------------------------------------------------------


async def test_tag_lp_handles_fenced_response():
    cand = _candidate("R1-01.1", "Identify letters.")
    payload = json.dumps(_valid_response(["R1-01.1"]))

    async def fake_llm(system: str, user: str) -> str:
        return f"```json\n{payload}\n```"

    result = await tag_lp("<p>lp</p>", [cand], llm=fake_llm)
    assert result.covered_sub_slo_ids == [cand["id"]]


async def test_tag_lp_drops_unknown_codes():
    cand = _candidate("R1-01.1", "Identify letters.")

    async def fake_llm(system: str, user: str) -> str:
        # LLM hallucinates a code that wasn't in candidates.
        return json.dumps(_valid_response(["R1-01.1", "R9-99.9"]))

    result = await tag_lp("<p>lp</p>", [cand], llm=fake_llm)
    assert result.covered_sub_slo_ids == [cand["id"]]


async def test_tag_lp_empty_response_raises():
    async def fake_llm(system: str, user: str) -> str:
        return ""

    with pytest.raises(ValueError, match="empty"):
        await tag_lp("<p>lp</p>", [], llm=fake_llm)


async def test_tag_lp_invalid_json_raises():
    async def fake_llm(system: str, user: str) -> str:
        return "not actually JSON at all"

    with pytest.raises(ValueError, match="invalid JSON"):
        await tag_lp("<p>lp</p>", [], llm=fake_llm)


async def test_tag_lp_no_candidates_still_returns_tags():
    """Edge case: caller has no candidates but still wants pedagogical tags."""

    async def fake_llm(system: str, user: str) -> str:
        return json.dumps(_valid_response([]))

    result = await tag_lp("<p>lp</p>", [], llm=fake_llm)
    assert result.covered_sub_slo_ids == []
    assert result.pedagogical_tags["bloom"] == "Remember"
