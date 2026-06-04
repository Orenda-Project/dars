"""
F1.9 — End-to-end smoke test of the v2 API against the seeded fixture.

This test is the canonical integration test for Phase 1 (D-19). It validates:
  - Migration applied (tables exist, queryable)
  - Seed loaded (lookups, SLOs, sub-SLOs, book, chapters, topics, tenancy)
  - All v2 read-only endpoints respond 200 with expected shape
  - Tenancy isolation: requests without the demo API key are rejected on
    org-scoped endpoints; curriculum/book endpoints are public

Runs against the test DB the same way other tests do — via ASGITransport
+ AsyncClient. Assumes the test DB has been migrated and seeded; CI
should run `make migrate && make seed` (or rely on lifespan auto-seed
during the AsyncClient startup).
"""
import os
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient


# The demo org's deterministic API key from F1.5 (D-65).
# Same value as in dars/seeds/tenancy_demo.py — duplicated here intentionally
# so the test is self-documenting.
DEMO_API_KEY = "dk_demo_dars_eng_g1_2dc7e0b8408142fa"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def auth_headers() -> dict[str, str]:
    return {"X-API-Key": DEMO_API_KEY}


async def _get(client: AsyncClient, path: str, *, auth: bool = False) -> dict:
    headers = auth_headers() if auth else {}
    resp = await client.get(path, headers=headers)
    assert resp.status_code == 200, f"{path} → {resp.status_code} {resp.text[:300]}"
    return resp.json()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("DATABASE_URL") is None,
    reason="v2 smoke test requires DATABASE_URL pointing at a seeded Postgres",
)
class TestV2Smoke:
    async def test_public_lookups(self, client: AsyncClient) -> None:
        grades = await _get(client, "/api/v2/grades")
        assert len(grades["items"]) == 12

        subjects = await _get(client, "/api/v2/subjects")
        codes = {s["code"] for s in subjects["items"]}
        assert codes >= {"Eng", "Urdu", "Maths", "Science", "GK", "Islamiat", "GenSci", "SST"}

        curriculums = await _get(client, "/api/v2/curriculums")
        codes = {c["code"] for c in curriculums["items"]}
        assert codes == {"DARS", "NCP", "SNC"}
        active = [c for c in curriculums["items"] if c["is_active"]]
        assert len(active) == 1 and active[0]["code"] == "DARS"

    async def test_slos_and_sub_slos(self, client: AsyncClient) -> None:
        # Resolve DARS curriculum / G1 / Eng.
        curriculums = await _get(client, "/api/v2/curriculums?is_active=true")
        dars_id = next(c["id"] for c in curriculums["items"] if c["code"] == "DARS")
        grades = await _get(client, "/api/v2/grades")
        g1_id = next(g["id"] for g in grades["items"] if g["code"] == 1)
        subjects = await _get(client, "/api/v2/subjects")
        eng_id = next(s["id"] for s in subjects["items"] if s["code"] == "Eng")

        slos = await _get(
            client,
            f"/api/v2/slos?curriculum_id={dars_id}&grade_id={g1_id}&subject_id={eng_id}",
        )
        assert len(slos["items"]) == 21, f"expected 21 SLOs, got {len(slos['items'])}"

        # Single SLO embeds its sub-SLOs.
        first_slo = slos["items"][0]
        detail = await _get(client, f"/api/v2/slos/{first_slo['id']}")
        assert len(detail["sub_slos"]) >= 3, f"first SLO should have ≥3 sub-SLOs"

        # All 5 valid lp_types should be represented across the 21 SLOs.
        slos_embed = await _get(
            client,
            f"/api/v2/slos?curriculum_id={dars_id}&grade_id={g1_id}&subject_id={eng_id}&include_sub_slos=true",
        )
        lp_types = {s["recommended_lp_type"] for s in slos_embed["items"]}
        assert lp_types == {
            "reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing"
        }
        total_sub_slos = sum(len(s["sub_slos"]) for s in slos_embed["items"])
        assert total_sub_slos == 71, f"expected 71 sub-SLOs, got {total_sub_slos}"

    async def test_books_and_chapters_and_topics(self, client: AsyncClient) -> None:
        curriculums = await _get(client, "/api/v2/curriculums?is_active=true")
        dars_id = next(c["id"] for c in curriculums["items"] if c["code"] == "DARS")
        grades = await _get(client, "/api/v2/grades")
        g1_id = next(g["id"] for g in grades["items"] if g["code"] == 1)
        subjects = await _get(client, "/api/v2/subjects")
        eng_id = next(s["id"] for s in subjects["items"] if s["code"] == "Eng")

        books = await _get(
            client,
            f"/api/v2/books?curriculum_id={dars_id}&grade_id={g1_id}&subject_id={eng_id}",
        )
        assert len(books["items"]) == 1
        book = books["items"][0]
        assert book["title"] == "Dars English Grade 1 Reader"
        assert book["total_chapters"] == 10
        # book_text excluded by default
        assert book.get("book_text") is None

        # ?include=book_text returns OCR payload
        detail = await _get(client, f"/api/v2/books/{book['id']}?include=book_text")
        assert detail["book_text"] is not None
        assert isinstance(detail["book_text"], list)
        assert len(detail["book_text"]) >= 30, "should be one OCR page per topic, ~31 total"

        # Chapters
        chapters = await _get(client, f"/api/v2/book-chapters?book_id={book['id']}")
        assert len(chapters["items"]) == 10
        chapter_titles = {c["title"] for c in chapters["items"]}
        assert "The Clever Crow" in chapter_titles
        assert "Hello, World" in chapter_titles

        # Chapter SLOs
        clever_crow = next(c for c in chapters["items"] if c["title"] == "The Clever Crow")
        chapter_slos = await _get(client, f"/api/v2/book-chapters/{clever_crow['id']}/slos")
        slo_codes = {s["code"] for s in chapter_slos["items"]}
        assert "R1-04" in slo_codes  # passage reading
        assert "C1-01" in slo_codes  # comprehension Q&A

        # Topics
        topics = await _get(client, f"/api/v2/topics?book_chapter_id={clever_crow['id']}")
        assert len(topics["items"]) >= 3
        assert all(t["topic_text"] for t in topics["items"]), "topic_text should always be set"

        # Topic sub-SLOs
        first_topic = topics["items"][0]
        topic_subs = await _get(client, f"/api/v2/topics/{first_topic['id']}/sub-slos")
        assert len(topic_subs["items"]) >= 2

    async def test_book_tree(self, client: AsyncClient) -> None:
        # Full nested tree (book-viewer F-1.1): book + book_text + chapters
        # (chapter_text + slos) + topics (topic_text + sub_slos), one payload.
        curriculums = await _get(client, "/api/v2/curriculums?is_active=true")
        dars_id = next(c["id"] for c in curriculums["items"] if c["code"] == "DARS")
        grades = await _get(client, "/api/v2/grades")
        g1_id = next(g["id"] for g in grades["items"] if g["code"] == 1)
        subjects = await _get(client, "/api/v2/subjects")
        eng_id = next(s["id"] for s in subjects["items"] if s["code"] == "Eng")
        books = await _get(
            client,
            f"/api/v2/books?curriculum_id={dars_id}&grade_id={g1_id}&subject_id={eng_id}",
        )
        book_id = books["items"][0]["id"]

        tree = await _get(client, f"/api/v2/books/{book_id}/tree")
        # OCR always included on the tree (D-3)
        assert isinstance(tree["book_text"], list) and len(tree["book_text"]) >= 30
        assert len(tree["chapters"]) == 10
        clever_crow = next(c for c in tree["chapters"] if c["title"] == "The Clever Crow")
        # chapter_text populated + linked SLOs nested in
        assert isinstance(clever_crow["chapter_text"], list)
        slo_codes = {s["code"] for s in clever_crow["slos"]}
        assert "R1-04" in slo_codes and "C1-01" in slo_codes
        # topics nested with topic_text + sub_slos
        assert len(clever_crow["topics"]) >= 3
        assert all(t["topic_text"] for t in clever_crow["topics"])
        assert any(len(t["sub_slos"]) >= 2 for t in clever_crow["topics"])

        # 404 on an unknown book
        resp = await client.get("/api/v2/books/00000000-0000-0000-0000-000000000000/tree")
        assert resp.status_code == 404

    async def test_tenancy_endpoints_require_api_key(self, client: AsyncClient) -> None:
        # Without key → 401
        resp = await client.get("/api/v2/orgs/me")
        assert resp.status_code == 401

        # With invalid key → 401
        resp = await client.get("/api/v2/orgs/me", headers={"X-API-Key": "bogus"})
        assert resp.status_code == 401

        # With demo key → 200
        org = await _get(client, "/api/v2/orgs/me", auth=True)
        assert org["name"] == "Dars Demo Org"
        assert org["api_key_prefix"] == "dk_demo_"

    async def test_tenancy_full_chain(self, client: AsyncClient) -> None:
        # Walk org → schools → teachers → AY → classes → CSTs
        schools = await _get(client, "/api/v2/schools", auth=True)
        assert len(schools["items"]) == 1
        school = schools["items"][0]
        assert school["name"] == "Dars Demo School"

        teachers = await _get(client, f"/api/v2/teachers?school_id={school['id']}", auth=True)
        assert len(teachers["items"]) == 1
        aisha = teachers["items"][0]
        assert aisha["name"] == "Aisha Khan"

        ays = await _get(client, f"/api/v2/academic-years?school_id={school['id']}", auth=True)
        assert len(ays["items"]) == 1
        ay = ays["items"][0]
        assert ay["name"] == "2026-2027"

        classes = await _get(
            client,
            f"/api/v2/classes?school_id={school['id']}&academic_year_id={ay['id']}",
            auth=True,
        )
        assert len(classes["items"]) == 1
        klass = classes["items"][0]
        assert klass["name"] == "Grade 1 - A"
        assert klass["section"] == "A"

        csts = await _get(
            client, f"/api/v2/csts?school_class_id={klass['id']}", auth=True,
        )
        assert len(csts["items"]) == 1
        cst = csts["items"][0]
        assert cst["teacher_id"] == aisha["id"]
        # List response shouldn't include the computed sequence position
        assert cst.get("current_sequence_position") in (None,)

        # Single-CST GET adds current_sequence_position
        cst_detail = await _get(client, f"/api/v2/csts/{cst['id']}", auth=True)
        assert cst_detail["current_sequence_position"] == 1

    async def test_404_on_unknown_uuid(self, client: AsyncClient) -> None:
        unknown = "00000000-0000-0000-0000-000000000000"
        # Public endpoint
        resp = await client.get(f"/api/v2/slos/{unknown}")
        assert resp.status_code == 404
        # Org-scoped
        resp = await client.get(f"/api/v2/schools/{unknown}", headers=auth_headers())
        assert resp.status_code == 404
