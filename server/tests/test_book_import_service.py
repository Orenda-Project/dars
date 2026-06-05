"""core-book-import F-1.4 — unit tests for the import service.

No live DB or LLM. Uses a fake asyncpg connection that scripts fetch* answers
and records executes, and a fake Anthropic client.
"""
import uuid

import pytest

from dars.v2_api import book_import_service as svc
from dars.v2_api.lp_type_classifier import classify_lp_type


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #


class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeUsage:
    input_tokens = 1
    output_tokens = 1
    cache_read_input_tokens = 0


class _FakeMessage:
    def __init__(self, text):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()


class _FakeMessages:
    def __init__(self, reply):
        self._reply = reply

    def create(self, **kwargs):
        return _FakeMessage(self._reply)


class _FakeAnthropic:
    """messages.create returns a fixed reply (for classify + mapping)."""
    def __init__(self, reply):
        self.messages = _FakeMessages(reply)


class _FakeConn:
    """Minimal asyncpg-conn stand-in. Records executes; scripted fetch answers."""
    def __init__(self, *, fetchval_map=None, fetchrow_map=None, fetch_map=None):
        self.executes = []
        self._fetchval_map = fetchval_map or {}
        self._fetchrow_map = fetchrow_map or {}
        self._fetch_map = fetch_map or {}

    async def execute(self, sql, *args):
        self.executes.append((" ".join(sql.split()), args))
        return "INSERT 0 1"

    async def fetchval(self, sql, *args):
        key = " ".join(sql.split())
        for frag, val in self._fetchval_map.items():
            if frag in key:
                return val(args) if callable(val) else val
        return None

    async def fetchrow(self, sql, *args):
        key = " ".join(sql.split())
        for frag, val in self._fetchrow_map.items():
            if frag in key:
                return val
        return None

    async def fetch(self, sql, *args):
        key = " ".join(sql.split())
        for frag, val in self._fetch_map.items():
            if frag in key:
                return val
        return []


# --------------------------------------------------------------------------- #
# lp_type classifier (mocked client)
# --------------------------------------------------------------------------- #


def test_classify_lp_type_maps_known_statement():
    client = _FakeAnthropic("grammar")
    out = classify_lp_type(
        parent_slo_statement="Use correct pronouns.",
        sub_slo_statement="Use 'he' and 'she' correctly.",
        client=client,
    )
    assert out == "grammar"


def test_classify_lp_type_retries_then_raises_on_garbage():
    client = _FakeAnthropic("not-a-real-type")
    with pytest.raises(ValueError):
        classify_lp_type(
            parent_slo_statement="x", sub_slo_statement="y", client=client,
        )


# --------------------------------------------------------------------------- #
# D-9 fix — robust parent-code derivation across all code formats
# --------------------------------------------------------------------------- #


def test_derive_parent_code_handles_all_formats():
    known = {"A-01", "A1-02", "B-3"}
    # dot-notation (the breakdown prompt's rule 6 format)
    assert svc._derive_parent_code("A-01.1", known) == "A-01"
    assert svc._derive_parent_code("A-01.10", known) == "A-01"
    # hyphen-letter (the original script's format)
    assert svc._derive_parent_code("A1-02-a", known) == "A1-02"
    assert svc._derive_parent_code("A1-02-aa", known) == "A1-02"
    # paren
    assert svc._derive_parent_code("B-3(2)", known) == "B-3"
    # unsplittable → bare parent code kept as-is
    assert svc._derive_parent_code("A-01", known) == "A-01"
    # prefix fallback for an odd separator
    assert svc._derive_parent_code("A1-02_x", known) == "A1-02"
    # genuinely unknown parent → None (skipped, warned)
    assert svc._derive_parent_code("Z-99.1", known) is None


def test_sub_code_sort_key_orders_numeric_then_alpha():
    codes = ["A-01.10", "A-01.2", "A-01.1"]
    assert sorted(codes, key=svc._sub_code_sort_key) == ["A-01.1", "A-01.2", "A-01.10"]
    alpha = ["A1-02-b", "A1-02-a", "A1-02-aa"]
    assert sorted(alpha, key=svc._sub_code_sort_key) == ["A1-02-a", "A1-02-b", "A1-02-aa"]


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #


def test_flatten_chapter_prose_joins_page_texts():
    pages = [{"pdf_page_no": 1, "text": "Page one."}, {"pdf_page_no": 2, "text": "Page two."}]
    assert svc._flatten_chapter_prose(pages) == "Page one.\n\nPage two."
    assert svc._flatten_chapter_prose([]) == ""


def test_parse_breakdown_markdown_reads_table_rows():
    md = (
        "| SLO Code | Main SLO (verbatim) | Sub SLO Code | Sub SLOs |\n"
        "| --- | --- | --- | --- |\n"
        "| A1-02 | Read words | A1-02-a | Read CVC words |\n"
    )
    rows = svc._parse_breakdown_markdown(md)
    assert rows == [{
        "SLO Code": "A1-02", "Main SLO (verbatim)": "Read words",
        "Sub SLO Code": "A1-02-a", "Sub SLOs": "Read CVC words",
    }]


def test_seed_uuid_is_deterministic_and_cell_scoped():
    a = svc.seed_uuid("book:NCP:G1:Eng:1171")
    b = svc.seed_uuid("book:NCP:G1:Eng:1171")
    c = svc.seed_uuid("book:DARS:G1:Eng:1171")
    assert a == b and a != c
    assert isinstance(a, uuid.UUID)


def test_grade_code_to_int():
    assert svc._grade_code_to_int("G1") == 1
    assert svc._grade_code_to_int("G12") == 12
    with pytest.raises(ValueError):
        svc._grade_code_to_int("KG")


# --------------------------------------------------------------------------- #
# resolve_cell error paths (422 upstream)
# --------------------------------------------------------------------------- #


async def test_resolve_cell_rejects_unknown_book():
    fde = _FakeConn(fetchrow_map={})  # book row -> None
    dars = _FakeConn()
    with pytest.raises(ValueError, match="not found"):
        await svc.resolve_cell(dars, fde, core_book_id=999, curriculum_id=None)


async def test_resolve_cell_rejects_non_onprod():
    fde = _FakeConn(fetchrow_map={
        "FROM fde_staging.book_library_book b":
            {"id": 1, "status": "Draft", "is_active": True, "grade": "G1", "subject": "Eng"},
    })
    dars = _FakeConn()
    with pytest.raises(ValueError, match="OnProd"):
        await svc.resolve_cell(dars, fde, core_book_id=1, curriculum_id=None)


async def test_resolve_cell_rejects_unmapped_grade():
    fde = _FakeConn(fetchrow_map={
        "FROM fde_staging.book_library_book b":
            {"id": 1, "status": "OnProd", "is_active": True, "grade": "G1", "subject": "Eng"},
    })
    # Dars has no grade row for code 1.
    dars = _FakeConn(fetchval_map={"FROM grades WHERE code": None})
    with pytest.raises(ValueError, match="no Dars grade"):
        await svc.resolve_cell(dars, fde, core_book_id=1, curriculum_id=None)


# --------------------------------------------------------------------------- #
# topics + mappings — null-prose warning path
# --------------------------------------------------------------------------- #


async def test_topics_warns_on_empty_prose_and_creates_topic():
    cell = {
        "curriculum_id": uuid.uuid4(), "curriculum_code": "NCP",
        "grade_id": uuid.uuid4(), "grade_code": "G1",
        "subject_id": uuid.uuid4(), "subject_code": "Eng",
    }
    chapters = [{"id": uuid.uuid4(), "chapter_number": 1, "title": "Empty Ch", "chapter_text": []}]
    topic_id = uuid.uuid4()
    dars = _FakeConn(
        fetchval_map={"SELECT id FROM topics": topic_id},
        fetch_map={"FROM sub_slos ss JOIN slos": []},
    )

    class _P:
        def __init__(self):
            self.warnings = []
        def warn(self, m):
            self.warnings.append(m)

    prog = _P()
    topics, mappings, bcs = await svc._import_topics_and_mappings(
        dars_conn=dars, chapters=chapters, cell=cell,
        sub_code_to_uuid={}, prog=prog, client=None,
    )
    assert topics == 1
    assert mappings == 0 and bcs == 0
    assert any("no prose" in w for w in prog.warnings)
    # a topics upsert happened
    assert any("INSERT INTO topics" in sql for sql, _ in dars.executes)
