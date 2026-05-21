"""
Claude-backed lp_type classifier for sub-SLOs (per D-11, D-14 of the
ncp-english-g1-seed feature).

Given a parent SLO statement + a sub-SLO statement, returns one of:
  reading | comprehension_word_meanings | comprehension_qa | grammar | creative_writing

Design notes:
- Uses the Anthropic SDK directly (already a dars dep).
- Model: claude-haiku-4-5 (cheap + sufficient for a 5-class classification).
- Prompt caching: the system block (enum definitions + few-shot examples) is
  marked cacheable, so a batch run of ~70 sub-SLOs reuses the prefix and
  reads from cache after the first call.
- temperature=0 for determinism. Haiku 4.5 still accepts temperature
  (unlike Opus 4.7, which removed sampling params).
- One retry on out-of-enum output with a stricter prompt; second miss raises.
"""
from __future__ import annotations

import logging
import os
from typing import Iterable

import anthropic

log = logging.getLogger(__name__)

VALID_LP_TYPES: frozenset[str] = frozenset({
    "reading",
    "comprehension_word_meanings",
    "comprehension_qa",
    "grammar",
    "creative_writing",
})

MODEL = "claude-haiku-4-5"

# System block — stable, cacheable.
SYSTEM_PROMPT = """You classify English-language sub-learning-outcomes for Grade 1 students into exactly one lesson-plan type.

The five valid lp_type values:

- reading: phonics, letter recognition, decoding, blending, sight words, fluency. Anything where the learner converts written letters/words into spoken sound.
  Example sub-SLO: "Blend three phonemes into a CVC word (e.g. /c/-/a/-/t/ -> cat)." -> reading

- comprehension_word_meanings: vocabulary, defining new words, synonyms, antonyms, picture-to-word matching. Knowing what a word MEANS.
  Example sub-SLO: "Identify the meaning of common animals' names from picture cues." -> comprehension_word_meanings

- comprehension_qa: answering questions about a passage, understanding what was read, recall of story details, inference. Working with meaning AFTER reading.
  Example sub-SLO: "Answer simple wh-questions about a read-aloud story (who, what, where)." -> comprehension_qa

- grammar: parts of speech, sentence structure, capitalisation, punctuation, plurals, pronouns, tenses, prepositions. Rules ABOUT language.
  Example sub-SLO: "Use 'a' and 'an' correctly before nouns starting with a consonant or vowel sound." -> grammar

- creative_writing: writing letters, words, or sentences; spelling; handwriting; composing simple stories or descriptions; letter formation.
  Example sub-SLO: "Write the lowercase letters a-z with correct letter formation." -> creative_writing

Return ONLY one of the five enum values. No explanation, no punctuation, no quotes."""


def _extract_text(response: anthropic.types.Message) -> str:
    """Return the concatenated text from a Message's content blocks."""
    return "".join(block.text for block in response.content if block.type == "text")


def classify_lp_type(
    *,
    parent_slo_statement: str,
    sub_slo_statement: str,
    client: anthropic.Anthropic | None = None,
) -> str:
    """
    Classify a sub-SLO into one of the five valid lp_type values.

    On invalid output, retries once with a stricter prompt. Second miss raises.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set; cannot classify lp_type")
        client = anthropic.Anthropic()

    user_message = (
        f"Parent SLO: {parent_slo_statement.strip()}\n"
        f"Sub-SLO: {sub_slo_statement.strip()}\n"
        f"Return only the enum value."
    )

    log.debug(
        "classify_lp_type request: parent=%r sub=%r",
        parent_slo_statement[:60],
        sub_slo_statement[:60],
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=32,
        temperature=0,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )
    candidate = _extract_text(response).strip().lower()

    if candidate in VALID_LP_TYPES:
        log.debug("classify_lp_type -> %s (cache_read=%s)", candidate,
                  response.usage.cache_read_input_tokens)
        return candidate

    # Retry once with stricter instruction.
    log.warning("classify_lp_type returned out-of-enum value %r; retrying", candidate)
    retry_user = user_message + (
        "\n\nIMPORTANT: your previous response was not one of the five valid values. "
        "Respond with EXACTLY one of: reading, comprehension_word_meanings, "
        "comprehension_qa, grammar, creative_writing. No other text."
    )
    response2 = client.messages.create(
        model=MODEL,
        max_tokens=32,
        temperature=0,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": retry_user}],
    )
    candidate2 = _extract_text(response2).strip().lower()
    if candidate2 in VALID_LP_TYPES:
        return candidate2

    raise ValueError(
        f"classify_lp_type produced invalid output twice for "
        f"sub-SLO {sub_slo_statement!r}: first={candidate!r}, second={candidate2!r}"
    )


def classify_all(
    records: Iterable[dict],
    *,
    client: anthropic.Anthropic | None = None,
) -> list[dict]:
    """
    Batch helper. `records` is an iterable of dicts with keys
    `parent_slo_statement` and `sub_slo_statement`; returns a list of the
    same dicts with `lp_type` populated. Sequential calls — the prompt-cache
    pays off after the first call.
    """
    if client is None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set; cannot classify lp_type")
        client = anthropic.Anthropic()

    out: list[dict] = []
    cache_reads = 0
    for i, record in enumerate(records):
        record = dict(record)  # don't mutate caller's dict
        record["lp_type"] = classify_lp_type(
            parent_slo_statement=record["parent_slo_statement"],
            sub_slo_statement=record["sub_slo_statement"],
            client=client,
        )
        out.append(record)
        if i == 0:
            log.info("classify_all: first request complete (cache warmup)")
        elif i % 10 == 0:
            log.info("classify_all: %d/%s processed", i, "?")
    log.info(
        "classify_all: %d records classified, cache reads observed: %s",
        len(out),
        cache_reads,
    )
    return out
