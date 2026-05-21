"""Unit tests for the Claude lp_type classifier."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lp_type_classifier import VALID_LP_TYPES, classify_lp_type


def _fake_response(text: str) -> SimpleNamespace:
    block = SimpleNamespace(type="text", text=text)
    usage = SimpleNamespace(cache_read_input_tokens=0)
    return SimpleNamespace(content=[block], usage=usage)


def _client_returning(*texts: str) -> MagicMock:
    """Build a mocked Anthropic client whose messages.create returns each text in turn."""
    client = MagicMock()
    client.messages.create.side_effect = [_fake_response(t) for t in texts]
    return client


def test_returns_valid_enum_value_on_first_try():
    client = _client_returning("grammar")
    result = classify_lp_type(
        parent_slo_statement="Identify parts of speech.",
        sub_slo_statement="Recognise nouns in a sentence.",
        client=client,
    )
    assert result == "grammar"
    assert client.messages.create.call_count == 1


def test_strips_whitespace_and_lowercases():
    client = _client_returning("  READING\n")
    result = classify_lp_type(
        parent_slo_statement="Decode CVC words.",
        sub_slo_statement="Blend three phonemes.",
        client=client,
    )
    assert result == "reading"


def test_retries_on_invalid_first_response():
    # Bad first response, valid second.
    client = _client_returning("not_a_valid_value", "comprehension_qa")
    result = classify_lp_type(
        parent_slo_statement="Understand a story.",
        sub_slo_statement="Answer who/what/where questions.",
        client=client,
    )
    assert result == "comprehension_qa"
    assert client.messages.create.call_count == 2


def test_raises_if_both_responses_invalid():
    client = _client_returning("bogus1", "bogus2")
    with pytest.raises(ValueError) as excinfo:
        classify_lp_type(
            parent_slo_statement="Foo.",
            sub_slo_statement="Bar.",
            client=client,
        )
    assert "bogus1" in str(excinfo.value)
    assert "bogus2" in str(excinfo.value)
    assert client.messages.create.call_count == 2


def test_request_uses_haiku_with_temperature_zero_and_cache_control():
    client = _client_returning("creative_writing")
    classify_lp_type(
        parent_slo_statement="Write simple sentences.",
        sub_slo_statement="Form the letter A.",
        client=client,
    )
    kwargs = client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5"
    assert kwargs["temperature"] == 0
    assert kwargs["max_tokens"] == 32
    # System block is cached.
    system_block = kwargs["system"][0]
    assert system_block["cache_control"] == {"type": "ephemeral"}
    # User message embeds both statements.
    user_content = kwargs["messages"][0]["content"]
    assert "Write simple sentences." in user_content
    assert "Form the letter A." in user_content


def test_valid_lp_types_constant_matches_documented_set():
    assert VALID_LP_TYPES == {
        "reading",
        "comprehension_word_meanings",
        "comprehension_qa",
        "grammar",
        "creative_writing",
    }
