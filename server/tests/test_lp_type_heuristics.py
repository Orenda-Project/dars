"""F2.5 — lp_type heuristic unit tests (D-68)."""
from dars.breakdown.lp_type_heuristics import pick_lp_type


def test_recommended_lp_type_wins_when_valid():
    # SLO author said 'grammar' — must override any keyword in the title.
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="Comprehension Questions",
        topic_text="Answer the questions below.",
        recommended_lp_type="grammar",
    ) == "grammar"


def test_recommended_lp_type_ignored_when_invalid_for_subject():
    # 'concrete' is Maths-only; on English we fall through to heuristic.
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="Comprehension Questions",
        topic_text="Answer the questions.",
        recommended_lp_type="concrete",
    ) == "comprehension_qa"


def test_grammar_keyword_matches():
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="Nouns",
        topic_text="A noun is a naming word.",
        recommended_lp_type=None,
    ) == "grammar"


def test_vocabulary_keyword_matches():
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="Word Meanings",
        topic_text="Learn the meanings of new words.",
        recommended_lp_type=None,
    ) == "comprehension_word_meanings"


def test_writing_keyword_matches():
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="Creative Writing",
        topic_text="Write a short story about your favourite animal.",
        recommended_lp_type=None,
    ) == "creative_writing"


def test_alphabet_topic_is_creative_writing():
    # "Letter formation" / "alphabet" keywords map to creative_writing.
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="The Alphabet",
        topic_text="Trace each letter.",
        recommended_lp_type=None,
    ) == "creative_writing"


def test_english_default_is_reading():
    assert pick_lp_type(
        subject_code="Eng",
        topic_title="Story: The Lost Kite",
        topic_text="Once upon a time...",
        recommended_lp_type=None,
    ) == "reading"


def test_maths_word_problems():
    assert pick_lp_type(
        subject_code="Maths",
        topic_title="Word Problems",
        topic_text="Ali has 5 apples...",
        recommended_lp_type=None,
    ) == "word_problems"


def test_maths_pictorial():
    assert pick_lp_type(
        subject_code="Maths",
        topic_title="Shapes",
        topic_text="Draw a circle and a square.",
        recommended_lp_type=None,
    ) == "pictorial_and_abstract"


def test_maths_default_is_concrete():
    assert pick_lp_type(
        subject_code="Maths",
        topic_title="Adding Numbers",
        topic_text="Learn how to add.",
        recommended_lp_type=None,
    ) == "concrete"


def test_science_falls_back_to_revision():
    assert pick_lp_type(
        subject_code="Science",
        topic_title="Plants",
        topic_text="A plant needs water.",
        recommended_lp_type=None,
    ) == "revision"


def test_unknown_subject_returns_safe_value():
    out = pick_lp_type(
        subject_code="Bogus",
        topic_title="Whatever",
        topic_text="",
        recommended_lp_type=None,
    )
    # Falls through to 'revision' (most subjects' last-resort).
    assert out == "revision"
