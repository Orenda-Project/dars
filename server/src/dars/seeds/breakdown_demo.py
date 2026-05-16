"""
F2.14 — Seed a published global → org → class breakdown for the demo
tenancy. After this runs, the demo CST has realized class_lesson_slots
and class_assessment_slots ready for Phase 3 (generation).

Idempotent: if a published global breakdown for (DARS, G1, Eng) already
exists with parent-or-self chains to the demo org and class, the whole
step is skipped.
"""
import logging

import asyncpg

from dars.breakdown.auto_build_service import (
    AutoBuildRequest,
    auto_build_breakdown,
)
from dars.breakdown.fork_service import fork_breakdown
from dars.breakdown.realize_service import realize_class_breakdown
from dars.seeds.lookups import seed_uuid

log = logging.getLogger("v2_seed.breakdown_demo")


async def _publish(conn: asyncpg.Connection, breakdown_id) -> None:
    await conn.execute(
        "UPDATE breakdowns SET status = 'published', updated_at = now() WHERE id = $1",
        breakdown_id,
    )


async def seed_demo_breakdown(conn: asyncpg.Connection) -> None:
    log.info("seed_demo_breakdown: starting")

    curriculum_id = seed_uuid("curriculum:DARS")
    grade_id = seed_uuid("grade:1")
    subject_id = seed_uuid("subject:Eng")
    org_id = seed_uuid("org:dars-demo-org")
    cst_id = seed_uuid("cst:dars-demo:g1-a:eng")

    # Resolve the book id for (DARS, G1, Eng).
    book_id = await conn.fetchval(
        """
        SELECT id FROM books
        WHERE curriculum_id = $1 AND grade_id = $2 AND subject_id = $3
        ORDER BY created_at LIMIT 1
        """,
        curriculum_id, grade_id, subject_id,
    )
    if book_id is None:
        log.warning(
            "seed_demo_breakdown: no book found for (DARS, G1, Eng) — F1.4 must run first"
        )
        return

    # Fast-path: published global already exists.
    global_published = await conn.fetchrow(
        """
        SELECT id FROM breakdowns
        WHERE scope = 'global' AND status = 'published'
          AND curriculum_id = $1 AND grade_id = $2 AND subject_id = $3
        ORDER BY created_at LIMIT 1
        """,
        curriculum_id, grade_id, subject_id,
    )

    if global_published is None:
        log.info("seed_demo_breakdown: building global draft via auto_build_breakdown")
        result = await auto_build_breakdown(
            conn,
            AutoBuildRequest(
                curriculum_id=curriculum_id,
                grade_id=grade_id,
                subject_id=subject_id,
                book_id=book_id,
                total_teaching_days=180,
                fa_cadence=5,
                sa_per_chapter=1,
                scope="global",
            ),
        )
        global_id = result.breakdown_id
        log.info(
            "seed_demo_breakdown: built global id=%s chapters=%d slots=%d",
            global_id, result.chapter_count, result.total_slot_count,
        )
        await _publish(conn, global_id)
    else:
        global_id = global_published["id"]
        log.info("seed_demo_breakdown: reusing published global id=%s", global_id)

    # Org-scope breakdown for the demo org.
    org_existing = await conn.fetchrow(
        """
        SELECT id, status FROM breakdowns
        WHERE scope = 'org' AND scope_ref_id = $1 AND status IN ('draft','published')
          AND curriculum_id = $2 AND grade_id = $3 AND subject_id = $4
        ORDER BY created_at LIMIT 1
        """,
        org_id, curriculum_id, grade_id, subject_id,
    )
    if org_existing is None:
        log.info("seed_demo_breakdown: forking global → org for demo org")
        org_breakdown_id, _, _ = await fork_breakdown(
            conn,
            source_id=global_id,
            new_scope="org",
            scope_ref_id=org_id,
        )
        await _publish(conn, org_breakdown_id)
    elif org_existing["status"] == "draft":
        org_breakdown_id = org_existing["id"]
        log.info("seed_demo_breakdown: publishing existing org draft id=%s", org_breakdown_id)
        await _publish(conn, org_breakdown_id)
    else:
        org_breakdown_id = org_existing["id"]
        log.info("seed_demo_breakdown: reusing published org id=%s", org_breakdown_id)

    # Class-scope breakdown for the demo CST.
    class_existing = await conn.fetchrow(
        """
        SELECT id, status FROM breakdowns
        WHERE scope = 'class' AND scope_ref_id = $1 AND status IN ('draft','published')
          AND curriculum_id = $2 AND grade_id = $3 AND subject_id = $4
        ORDER BY created_at LIMIT 1
        """,
        cst_id, curriculum_id, grade_id, subject_id,
    )
    if class_existing is None:
        log.info("seed_demo_breakdown: forking org → class for demo CST")
        class_breakdown_id, _, _ = await fork_breakdown(
            conn,
            source_id=org_breakdown_id,
            new_scope="class",
            scope_ref_id=cst_id,
        )
        await _publish(conn, class_breakdown_id)
        log.info("seed_demo_breakdown: realizing class breakdown id=%s", class_breakdown_id)
        realized = await realize_class_breakdown(conn, class_breakdown_id)
        log.info(
            "seed_demo_breakdown: realize done lessons=%d assessments=%d",
            realized.lesson_slots_upserted, realized.assessment_slots_upserted,
        )
    elif class_existing["status"] == "draft":
        class_breakdown_id = class_existing["id"]
        log.info("seed_demo_breakdown: publishing existing class draft id=%s", class_breakdown_id)
        await _publish(conn, class_breakdown_id)
        await realize_class_breakdown(conn, class_breakdown_id)
    else:
        class_breakdown_id = class_existing["id"]
        log.info("seed_demo_breakdown: reusing published class id=%s", class_breakdown_id)
        # Ensure realization is up to date (idempotent upsert).
        await realize_class_breakdown(conn, class_breakdown_id)

    lesson_count = await conn.fetchval(
        "SELECT COUNT(*) FROM class_lesson_slots WHERE cst_id = $1", cst_id
    )
    assess_count = await conn.fetchval(
        "SELECT COUNT(*) FROM class_assessment_slots WHERE cst_id = $1", cst_id
    )
    log.info(
        "seed_demo_breakdown: done — global=%s org=%s class=%s lesson_slots=%d assessment_slots=%d",
        global_id, org_breakdown_id, class_breakdown_id, lesson_count, assess_count,
    )
