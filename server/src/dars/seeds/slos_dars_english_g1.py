"""
F1.3 — SLO + Sub-SLO seed for Dars Curriculum × Grade 1 × English.

🧊 SEED FREEZE: After this file lands on staging and is reviewed by the
user, the SLO codes and sub-SLO codes here become FROZEN. Phase 2+ code
references them by code (e.g. R1-02-a). Adding new SLOs/sub-SLOs is fine;
renaming or renumbering existing ones requires explicit user approval and
a decision-log entry per REBUILD.md Step 9.

Domain structure is bound to LP Assistant's lp_type enum so the breakdown
engine never has to guess which prompt to use:

- R: Decoding & fluency       → lp_type=reading
- V: Vocabulary               → lp_type=comprehension_word_meanings
- C: Comprehension            → lp_type=comprehension_qa
- G: Grammar                  → lp_type=grammar
- W: Writing                  → lp_type=creative_writing

Listening (L) and Speaking (S) are intentionally excluded in v1 because
LP Assistant has no corresponding lp_type. They can be added when
upstream support lands (D-61 successor decision).

Codes use pattern `{Domain}{Grade}-{NN}`; sub-SLOs use `{Domain}{Grade}-{NN}-{a|b|c|d|e}`.
Codes are GLOBAL across the (curriculum, grade, subject) tuple — uniqueness enforced by DB.
"""
import logging

import asyncpg

from dars.seeds.lookups import seed_uuid

log = logging.getLogger("v2_seed.slos_dars_english_g1")


# ---------------------------------------------------------------------------
# SLO + sub-SLO definitions
# ---------------------------------------------------------------------------
# Each entry: (code, statement, recommended_lp_type, [(sub_code_suffix, sub_statement), ...])

DECODING = [
    (
        "R1-01",
        "Identify and name all 26 letters of the English alphabet.",
        "reading",
        [
            ("a", "Identifies all uppercase letters A–Z when shown out of order."),
            ("b", "Identifies all lowercase letters a–z when shown out of order."),
            ("c", "Matches each uppercase letter to its lowercase form."),
            ("d", "Names the letter when shown a printed example."),
        ],
    ),
    (
        "R1-02",
        "Read simple CVC (consonant-vowel-consonant) words.",
        "reading",
        [
            ("a", "Blends three individual phonemes into a word (e.g. /c/-/a/-/t/ → cat)."),
            ("b", "Reads CVC words with short /a/ sound (cat, hat, man, bag)."),
            ("c", "Reads CVC words with short /e/, /i/, /o/, /u/ sounds."),
            ("d", "Reads CVC words at sight without sounding out, with practice."),
        ],
    ),
    (
        "R1-03",
        "Read high-frequency sight words appropriate for Grade 1.",
        "reading",
        [
            ("a", "Reads 20 most-frequent sight words (the, a, is, in, it, and, to, of, …)."),
            ("b", "Recognizes sight words within a sentence context."),
            ("c", "Reads numbers one through ten as words."),
        ],
    ),
    (
        "R1-04",
        "Read short sentences and short passages aloud with appropriate pacing.",
        "reading",
        [
            ("a", "Reads a five- to seven-word sentence aloud without stopping mid-word."),
            ("b", "Uses end punctuation as a pause cue (full stop, question mark)."),
            ("c", "Reads a short three- to five-sentence passage with one helping prompt or fewer."),
            ("d", "Self-corrects when a word doesn't make sense in context."),
        ],
    ),
]

VOCABULARY = [
    (
        "V1-01",
        "Understand vocabulary for self, family, and home.",
        "comprehension_word_meanings",
        [
            ("a", "Names immediate family members in English (mother, father, sister, brother)."),
            ("b", "Names common rooms or parts of a home."),
            ("c", "Names common items found at home (bed, table, lamp, …)."),
        ],
    ),
    (
        "V1-02",
        "Understand vocabulary for school, classroom, and daily routine.",
        "comprehension_word_meanings",
        [
            ("a", "Names common classroom objects (book, pencil, board, desk)."),
            ("b", "Names parts of the school day (morning, recess, home time)."),
            ("c", "Names common subjects (English, Maths, Science)."),
            ("d", "Uses verbs for daily routine (eat, sleep, study, play) in modeled phrases."),
        ],
    ),
    (
        "V1-03",
        "Understand vocabulary for colours, numbers, shapes, and the body.",
        "comprehension_word_meanings",
        [
            ("a", "Names eight to ten colours."),
            ("b", "Says number words one through twenty."),
            ("c", "Names basic shapes (circle, square, triangle, rectangle)."),
            ("d", "Names main body parts (head, eye, ear, mouth, hand, leg)."),
        ],
    ),
    (
        "V1-04",
        "Infer the meaning of unfamiliar words from context in a simple sentence.",
        "comprehension_word_meanings",
        [
            ("a", "Uses surrounding words in a sentence to guess a word's meaning."),
            ("b", "Recognizes that two different words can mean similar things (simple synonyms)."),
            ("c", "Recognizes that two different words can mean opposite things (simple antonyms: big/small, hot/cold)."),
        ],
    ),
]

COMPREHENSION = [
    (
        "C1-01",
        "Answer literal who/what/where questions about a short passage.",
        "comprehension_qa",
        [
            ("a", "Identifies who is in a story (main character)."),
            ("b", "Identifies where a story takes place (setting)."),
            ("c", "Names what the main character did in one event."),
        ],
    ),
    (
        "C1-02",
        "Recall key events from a short story in correct sequence.",
        "comprehension_qa",
        [
            ("a", "Recalls one event from a story they have read or heard."),
            ("b", "Identifies what happened first and what happened last."),
            ("c", "Retells a three- to four-event story in correct order, with prompts."),
        ],
    ),
    (
        "C1-03",
        "Identify the main idea or lesson of a short story.",
        "comprehension_qa",
        [
            ("a", "Answers 'What is the story about?' in a single sentence."),
            ("b", "States a simple lesson learned (kindness, honesty, sharing) when prompted."),
            ("c", "Distinguishes between the main idea and a small detail in a story."),
        ],
    ),
]

GRAMMAR = [
    (
        "G1-01",
        "Distinguish between common nouns and proper nouns.",
        "grammar",
        [
            ("a", "Identifies whether a given word names a person, place, or thing."),
            ("b", "Capitalises the first letter of a proper noun (own name, city name)."),
            ("c", "Uses 'a' or 'an' correctly before a common noun in modeled sentences."),
        ],
    ),
    (
        "G1-02",
        "Use singular and plural forms of common nouns.",
        "grammar",
        [
            ("a", "Adds -s to form a regular plural (book → books)."),
            ("b", "Uses common irregular plurals correctly (man/men, child/children, mouse/mice) in modeled phrases."),
            ("c", "Selects between singular and plural form for a sentence."),
        ],
    ),
    (
        "G1-03",
        "Use action verbs in simple present tense.",
        "grammar",
        [
            ("a", "Identifies the action word in a simple sentence."),
            ("b", "Uses 'I run / She runs' style present tense in a complete sentence."),
            ("c", "Adds -s for third-person singular present (he runs, she plays)."),
        ],
    ),
    (
        "G1-04",
        "Use simple pronouns (I, you, he, she, it, we, they).",
        "grammar",
        [
            ("a", "Replaces a name with the correct pronoun in a modeled sentence."),
            ("b", "Uses 'I' to refer to self."),
            ("c", "Uses 'he' / 'she' to refer to a male or female person."),
            ("d", "Uses 'it' for objects or animals."),
        ],
    ),
    (
        "G1-05",
        "Use common prepositions of place (in, on, under, next to).",
        "grammar",
        [
            ("a", "Describes the location of an object using 'in', 'on', or 'under'."),
            ("b", "Selects the correct preposition for a simple picture-based prompt."),
            ("c", "Uses 'next to' to describe two adjacent objects."),
        ],
    ),
]

WRITING = [
    (
        "W1-01",
        "Form all 26 letters of the alphabet with correct strokes and proportion.",
        "creative_writing",
        [
            ("a", "Writes uppercase letters A–Z with correct starting point and stroke order."),
            ("b", "Writes lowercase letters a–z with correct strokes."),
            ("c", "Maintains letter size proportional to lines on ruled paper."),
            ("d", "Forms letters legibly without significant reversals (e.g. b/d, p/q)."),
        ],
    ),
    (
        "W1-02",
        "Spell common CVC and high-frequency sight words from memory.",
        "creative_writing",
        [
            ("a", "Spells 15 common CVC words on dictation (cat, dog, bed, …)."),
            ("b", "Spells 10 high-frequency sight words from memory."),
            ("c", "Uses sound-letter correspondence to attempt unfamiliar simple words."),
        ],
    ),
    (
        "W1-03",
        "Write own name and simple personal information.",
        "creative_writing",
        [
            ("a", "Writes own first name in correct order."),
            ("b", "Writes own age in numeric form."),
            ("c", "Writes the name of their class or school in two to three words."),
        ],
    ),
    (
        "W1-04",
        "Construct simple sentences using a subject and verb.",
        "creative_writing",
        [
            ("a", "Writes a sentence beginning with a capital letter and ending with a full stop."),
            ("b", "Uses 'I am …' / 'I have …' / 'This is …' sentence frames correctly."),
            ("c", "Writes a sentence describing a picture (one to two sentences)."),
            ("d", "Leaves appropriate space between words."),
        ],
    ),
    (
        "W1-05",
        "Write a short two- to three-sentence description of a picture or familiar object.",
        "creative_writing",
        [
            ("a", "Writes two sentences describing what is in a picture."),
            ("b", "Uses at least one adjective (colour, size) to describe."),
            ("c", "Sentences are intelligible to another reader."),
        ],
    ),
]


# Flatten in canonical order for stable position assignment.
ALL_SLOS = DECODING + VOCABULARY + COMPREHENSION + GRAMMAR + WRITING


# ---------------------------------------------------------------------------
# Insert
# ---------------------------------------------------------------------------


async def seed_dars_english_g1_slos(conn: asyncpg.Connection) -> None:
    log.info("seed_dars_english_g1_slos: starting")

    # Resolve FK targets (already seeded by F1.2).
    curriculum_id = seed_uuid("curriculum:DARS")
    grade_id = seed_uuid("grade:1")
    subject_id = seed_uuid("subject:Eng")

    # Sanity: SLO codes must be unique across the seed file.
    seen_codes: set[str] = set()
    for code, _statement, _lp_type, sub_slos in ALL_SLOS:
        assert code not in seen_codes, f"duplicate SLO code: {code}"
        seen_codes.add(code)
        sub_codes_for_slo: set[str] = set()
        for suffix, _ in sub_slos:
            sub_code = f"{code}-{suffix}"
            assert sub_code not in sub_codes_for_slo, f"duplicate sub-SLO code: {sub_code}"
            sub_codes_for_slo.add(sub_code)

    # Fast-path: skip the heavy work if everything's already in.
    existing_slo_count = await conn.fetchval(
        "SELECT COUNT(*) FROM slos WHERE curriculum_id=$1 AND grade_id=$2 AND subject_id=$3",
        curriculum_id, grade_id, subject_id,
    )
    expected_total_sub_slos = sum(len(subs) for _, _, _, subs in ALL_SLOS)
    existing_sub_slo_count = await conn.fetchval(
        """
        SELECT COUNT(*) FROM sub_slos ss
        JOIN slos s ON s.id = ss.slo_id
        WHERE s.curriculum_id=$1 AND s.grade_id=$2 AND s.subject_id=$3
        """,
        curriculum_id, grade_id, subject_id,
    )
    if existing_slo_count == len(ALL_SLOS) and existing_sub_slo_count == expected_total_sub_slos:
        log.info(
            "seed_dars_english_g1_slos: already complete (slos=%d, sub_slos=%d) — skipping",
            existing_slo_count, existing_sub_slo_count,
        )
        return

    slos_inserted = 0
    sub_slos_inserted = 0
    for slo_position, (code, statement, lp_type, sub_slos) in enumerate(ALL_SLOS, start=1):
        slo_id = seed_uuid(f"slo:DARS:1:Eng:{code}")
        result = await conn.execute(
            """
            INSERT INTO slos (id, curriculum_id, grade_id, subject_id, code, statement, position, recommended_lp_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (curriculum_id, grade_id, subject_id, code) DO NOTHING
            """,
            slo_id, curriculum_id, grade_id, subject_id, code, statement, slo_position, lp_type,
        )
        if result.endswith(" 1"):
            slos_inserted += 1

        for sub_position, (suffix, sub_statement) in enumerate(sub_slos, start=1):
            sub_code = f"{code}-{suffix}"
            sub_id = seed_uuid(f"sub_slo:DARS:1:Eng:{sub_code}")
            sub_result = await conn.execute(
                """
                INSERT INTO sub_slos (id, slo_id, code, statement, position, source)
                VALUES ($1, $2, $3, $4, $5, 'manual')
                ON CONFLICT (slo_id, code) DO NOTHING
                """,
                sub_id, slo_id, sub_code, sub_statement, sub_position,
            )
            if sub_result.endswith(" 1"):
                sub_slos_inserted += 1

    log.info(
        "seed_dars_english_g1_slos: done — slos=%d (inserted=%d), sub_slos=%d (inserted=%d)",
        len(ALL_SLOS), slos_inserted, expected_total_sub_slos, sub_slos_inserted,
    )
