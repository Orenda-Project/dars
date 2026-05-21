"""
F2.5 — lp_type heuristic table (D-68).

Picks an lp_type for a topic. Precedence (highest first):
  1. A sub-SLO's `recommended_lp_type` if one is set (most specific signal —
     populated per-sub-SLO by the NCP seed via Claude classification, see
     D-11/D-13 in docs/features/ncp-english-g1-seed/).
  2. The parent SLO's `recommended_lp_type` (set by curriculum authors at
     SLO authoring time — used by the existing Dars seed where sub-SLOs are
     NULL).
  3. Keyword matching against topic title + first 200 chars of topic_text.
  4. Default to subject-specific safe fallback ('reading' for Eng/Urdu,
     'concrete' for Maths, 'revision' otherwise).

LLM fallback is intentionally out of scope here; F2.5 calls into this
table only. When (heuristic returns None AND topic looks ambiguous),
the caller may invoke the LLM separately.
"""
from dars.v2_api.lp_types import is_valid_lp_type, valid_lp_types_for_subject


# Keyword → lp_type. Order matters when multiple keywords match: first
# match wins, so list more-specific / higher-confidence keywords first.
# Keywords are matched as lowercase substrings on (title + " " + first 200
# chars of topic_text).
_ENG_URDU_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    # Vocabulary / word meanings
    (("vocabulary", "word meanings", "word meaning", "synonyms", "antonyms"), "comprehension_word_meanings"),
    # Grammar
    (("grammar", "noun", "nouns", "verb", "verbs", "pronoun", "pronouns",
      "adjective", "adjectives", "tense", "tenses", "sentence structure",
      "punctuation", "preposition", "prepositions"), "grammar"),
    # Writing / spelling / letter formation
    (("spelling", "creative writing", "story writing", "paragraph writing",
      "letter writing", "write a", "writing"), "creative_writing"),
    # Letters (alphabet) — match standalone "letters" / "alphabet"
    (("alphabet", "letters of the", "letter formation"), "creative_writing"),
    # Comprehension Q&A
    (("comprehension", "answer the questions", "answer the question",
      "questions and answers", "q&a"), "comprehension_qa"),
    # Reading is the catch-all for Eng/Urdu, applied as default below.
]

_MATHS_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("word problem", "word problems", "story sum", "story problem"), "word_problems"),
    (("picture", "pictorial", "draw", "shapes", "diagram"), "pictorial_and_abstract"),
    (("counting", "use blocks", "manipulative", "objects", "fingers"), "concrete"),
]

_SUBJECT_KEYWORDS: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "Eng": _ENG_URDU_KEYWORDS,
    "Urdu": _ENG_URDU_KEYWORDS,
    "Maths": _MATHS_KEYWORDS,
}

# Last-resort fallback per subject.
_DEFAULT_LP_TYPE: dict[str, str] = {
    "Eng": "reading",
    "Urdu": "reading",
    "Maths": "concrete",
    "Science": "revision",
    "GK": "revision",
}


def _match_signal(text: str, table: list[tuple[tuple[str, ...], str]]) -> str | None:
    text_l = text.lower()
    for needles, lp_type in table:
        for needle in needles:
            if needle in text_l:
                return lp_type
    return None


def pick_lp_type(
    *,
    subject_code: str,
    topic_title: str | None,
    topic_text: str | None,
    recommended_lp_type: str | None,
    sub_slo_recommended_lp_type: str | None = None,
) -> str:
    """
    Resolve the lp_type for a topic.

    Precedence: sub-SLO recommended > parent SLO recommended > keyword
    heuristic > per-subject default. Both recommended inputs are validated
    against the subject's allowed set before being used; an invalid value
    falls through to the next tier instead of being silently substituted.

    Returns a value guaranteed valid for `subject_code` (per
    lp_types.LP_TYPES_BY_SUBJECT). Never returns None.
    """
    # 1. Sub-SLO's intent wins if it's valid for the subject (D-13).
    if sub_slo_recommended_lp_type and is_valid_lp_type(subject_code, sub_slo_recommended_lp_type):
        return sub_slo_recommended_lp_type

    # 2. Parent SLO author's intent.
    if recommended_lp_type and is_valid_lp_type(subject_code, recommended_lp_type):
        return recommended_lp_type

    # 3. Keyword heuristic on title + first 200 chars of topic_text (D-68).
    title = topic_title or ""
    text_head = (topic_text or "")[:200]
    haystack = f"{title} {text_head}".strip()
    table = _SUBJECT_KEYWORDS.get(subject_code, [])
    if table and haystack:
        match = _match_signal(haystack, table)
        if match and is_valid_lp_type(subject_code, match):
            return match

    # 4. Per-subject default; double-check it's in the valid set.
    fallback = _DEFAULT_LP_TYPE.get(subject_code, "revision")
    if not is_valid_lp_type(subject_code, fallback):
        return "revision" if "revision" in valid_lp_types_for_subject(subject_code) else fallback
    return fallback
