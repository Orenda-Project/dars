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
        self.stop_reason = "end_turn"


class _FakeStream:
    def __init__(self, reply):
        self._reply = reply

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get_final_message(self):
        return _FakeMessage(self._reply)


class _FakeMessages:
    def __init__(self, reply):
        self._reply = reply

    def create(self, **kwargs):
        return _FakeMessage(self._reply)

    def stream(self, **kwargs):
        return _FakeStream(self._reply)


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
# LLM call logging — entry + exit (usage) so imports are debuggable from logs
# --------------------------------------------------------------------------- #


async def test_chapter_map_logs_and_filters(caplog):
    import logging
    client = _FakeAnthropic("A-01.1\nbogus-code")
    with caplog.at_level(logging.INFO, logger="dars.v2_api.book_import_service"):
        out = await svc._map_chapter_to_sub_slos(
            chapter_title="Colours", chapter_prose="red and blue",
            sub_slo_index_text="- A-01.1: x", valid_codes={"A-01.1"}, client=client,
        )
    assert out == ["A-01.1"]  # bogus-code filtered out
    text = caplog.text
    # _complete logs start/done with the label; the helper logs matched/dropped.
    assert "chapter-map" in text and "Colours" in text
    assert "matched=1" in text and "dropped=1" in text


def test_usage_str_tolerates_missing_usage():
    class _NoUsage:
        pass
    assert svc._usage_str(_NoUsage()) == "usage=n/a"


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
        "FROM book_library_book b":
            {"id": 1, "status": "Draft", "is_active": True, "grade": "G1", "subject": "Eng"},
    })
    dars = _FakeConn()
    with pytest.raises(ValueError, match="OnProd"):
        await svc.resolve_cell(dars, fde, core_book_id=1, curriculum_id=None)


async def test_resolve_cell_rejects_unmapped_grade():
    fde = _FakeConn(fetchrow_map={
        "FROM book_library_book b":
            {"id": 1, "status": "OnProd", "is_active": True, "grade": "G1", "subject": "Eng"},
    })
    # Dars has no grade row for code 1.
    dars = _FakeConn(fetchval_map={"FROM grades WHERE code": None})
    with pytest.raises(ValueError, match="no Dars grade"):
        await svc.resolve_cell(dars, fde, core_book_id=1, curriculum_id=None)


# --------------------------------------------------------------------------- #
# topics + mappings — null-prose warning path
# --------------------------------------------------------------------------- #


class _ProgStub:
    """Minimal _Progress stand-in for write/plan tests."""
    def __init__(self):
        self.warnings = []
        self.steps = {}
        self.counts = {}
        self.dars_book_id = None
    def warn(self, m):
        self.warnings.append(m)
    async def start_step(self, conn, step):
        self.steps[step] = {"status": "running"}
    async def finish_step(self, conn, step, count):
        self.steps[step] = {"status": "done", "count": count}
        self.counts[step] = count
    async def _flush(self, conn, *, status):
        pass


async def test_write_import_plan_writes_book_subslos_topics():
    # Phase B: given a fully-built plan, write it with no post-insert SELECTs
    # (deterministic UUIDs are the ids). Verify each table is upserted.
    cell = {
        "curriculum_id": uuid.uuid4(), "curriculum_code": "NCP",
        "grade_id": uuid.uuid4(), "grade_code": "G1",
        "subject_id": uuid.uuid4(), "subject_code": "Eng",
    }
    slo_id, sub_id, book_id, ch_id, topic_id = (uuid.uuid4() for _ in range(5))
    plan = {
        "slos": [{"id": slo_id, "code": "A-01", "statement": "s", "position": 1}],
        "sub_slos": [{"id": sub_id, "slo_id": slo_id, "code": "A-01.1",
                      "statement": "ss", "position": 1, "lp_type": "reading"}],
        "sub_code_to_uuid": {"A-01.1": sub_id},
        "book": {"id": book_id, "title": "B", "publisher": None, "edition": None,
                 "published_year": None, "total_chapters": 1, "pdf_url": None, "book_text": []},
        "chapters": [{"id": ch_id, "book_id": book_id, "chapter_number": 1, "title": "Ch1",
                      "start_page": 1, "end_page": 2, "status": "published", "chapter_text": []}],
        "topics": [{"id": topic_id, "book_chapter_id": ch_id, "title": "Ch1",
                    "topic_text": "x", "sub_slo_codes": ["A-01.1"]}],
    }
    dars = _FakeConn(fetchval_map={"SELECT slo_id FROM sub_slos": slo_id})
    prog = _ProgStub()
    await svc._write_import_plan(dars_conn=dars, cell=cell, plan=plan, prog=prog)

    sqls = [sql for sql, _ in dars.executes]
    assert any("INSERT INTO slos" in s for s in sqls)
    assert any("INSERT INTO sub_slos" in s for s in sqls)
    assert any("INSERT INTO books" in s for s in sqls)
    assert any("INSERT INTO book_chapters" in s for s in sqls)
    assert any("INSERT INTO topics" in s for s in sqls)
    assert any("INSERT INTO topic_sub_slos" in s for s in sqls)
    assert any("INSERT INTO book_chapter_slos" in s for s in sqls)
    # No post-insert SELECT round-trips (the hang fix relies on this).
    assert not any(s.strip().upper().startswith("SELECT ID FROM") for s in sqls)
    assert prog.dars_book_id == book_id
    assert prog.counts.get("sub_slos") == 1
