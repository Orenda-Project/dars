"""
F2.3 — prompt_store coverage test.

Every registered prompt key must resolve to a non-empty .txt file in
src/dars/breakdown/prompts/. Catches missed copies / typos at CI time.
"""
import pytest

from dars.breakdown.prompt_store import _PROMPT_FILES, get_prompt


@pytest.mark.parametrize("key", sorted(_PROMPT_FILES))
def test_every_registered_prompt_resolves(key: str) -> None:
    text = get_prompt(key)
    assert text and text.strip(), f"prompt {key!r} loaded empty"


def test_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        get_prompt("nope_not_a_real_key")


def test_expected_keys_present() -> None:
    expected = {
        "english_slo_breakdown",
        "math_slo_breakdown",
        "urdu_slo_breakdown",
        "topic_breakdown",
        "chapter_plan",
        "slo_mapping",
        "lp_tagging",
    }
    assert expected.issubset(set(_PROMPT_FILES))
