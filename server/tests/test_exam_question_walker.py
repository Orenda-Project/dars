"""
F3.9 — iter_questions walks the exam_json structure deterministically.

Pure-Python: covers the parser only. Tagging-against-DB cases are in
the DB-gated integration tests.
"""
from dars.generated_exams.tagging_service import iter_questions


def test_walks_objective_and_subjective_in_order():
    exam_json = {
        "unseen": {
            "objective": {
                "MCQs": [
                    {"main_question": "Q1", "question": "Choose A or B", "marks": 1},
                    {"main_question": "Q2", "question": "Choose C or D", "marks": 1},
                ],
                "True/False": [
                    {"question": "The sky is blue.", "marks": 1},
                ],
            },
            "subjective": {
                "Brief Answers": [
                    {"main_question": "Answer briefly", "question": "Why?", "marks": 2},
                ],
            },
        }
    }
    questions = list(iter_questions(exam_json))
    keys = [k for k, _, _ in questions]
    assert keys == [
        "unseen:objective:MCQs:0",
        "unseen:objective:MCQs:1",
        "unseen:objective:True/False:0",
        "unseen:subjective:Brief Answers:0",
    ]
    assert questions[0][1].startswith("Q1\n")
    assert questions[2][1] == "The sky is blue."


def test_skips_empty_or_malformed_items():
    exam_json = {
        "unseen": {
            "objective": {
                "MCQs": [
                    {"question": "ok"},
                    {},                     # no usable text — skip
                    "not a dict",           # malformed — skip
                ],
            }
        }
    }
    questions = list(iter_questions(exam_json))
    assert [k for k, _, _ in questions] == ["unseen:objective:MCQs:0"]


def test_empty_exam_json_yields_nothing():
    assert list(iter_questions({})) == []
    assert list(iter_questions(None)) == []
