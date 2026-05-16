"""
F2.7 — Fork a Breakdown to a new scope (deep-copy + reparent).

`fork_breakdown(conn, source_id, new_scope, scope_ref_id)` returns the
new draft breakdown's id. All inserts run in one transaction.

Constraints per the phase doc:
  - source must be `status='published'`
  - org can only have one breakdown per (curriculum, grade, subject)
    that is currently draft. A published org breakdown is fine — the
    fork becomes a new draft "version" referencing the published one
    via parent_breakdown_id; the caller can then PATCH/publish.
  - same for class scope.

Returns (new_id, copied_chapter_count, copied_slot_count).
"""
import logging
from uuid import UUID

import asyncpg

log = logging.getLogger("breakdown.fork")


VALID_FORK_TARGETS = {"org", "class"}


async def _ensure_no_existing_draft_for_scope(
    conn: asyncpg.Connection,
    *,
    scope: str,
    scope_ref_id: UUID,
    curriculum_id: UUID,
    grade_id: UUID,
    subject_id: UUID,
) -> None:
    existing = await conn.fetchval(
        """
        SELECT 1 FROM breakdowns
        WHERE scope = $1 AND scope_ref_id = $2
          AND curriculum_id = $3 AND grade_id = $4 AND subject_id = $5
          AND status = 'draft'
        LIMIT 1
        """,
        scope, scope_ref_id, curriculum_id, grade_id, subject_id,
    )
    if existing:
        raise ValueError(
            f"a draft breakdown already exists for {scope}={scope_ref_id} on "
            f"(curriculum, grade, subject); publish or delete it first"
        )


async def fork_breakdown(
    conn: asyncpg.Connection,
    *,
    source_id: UUID,
    new_scope: str,
    scope_ref_id: UUID,
) -> tuple[UUID, int, int]:
    log.info(
        "fork_breakdown: source=%s new_scope=%s scope_ref_id=%s",
        source_id, new_scope, scope_ref_id,
    )
    if new_scope not in VALID_FORK_TARGETS:
        raise ValueError(f"new_scope must be one of {sorted(VALID_FORK_TARGETS)}")

    source = await conn.fetchrow(
        """
        SELECT id, scope, curriculum_id, grade_id, subject_id, book_id,
               total_teaching_days, status
        FROM breakdowns
        WHERE id = $1
        """,
        source_id,
    )
    if source is None:
        raise ValueError(f"source breakdown {source_id} not found")
    if source["status"] != "published":
        raise ValueError(
            f"source breakdown is {source['status']!r}; only published breakdowns can be forked"
        )

    # Parent-scope sanity: org forks from global, class forks from org.
    if new_scope == "org" and source["scope"] != "global":
        raise ValueError("fork-org requires source.scope='global'")
    if new_scope == "class" and source["scope"] != "org":
        raise ValueError("fork-class requires source.scope='org'")

    # Verify the target ref exists.
    if new_scope == "org":
        ok = await conn.fetchval("SELECT 1 FROM organizations WHERE id = $1", scope_ref_id)
        if not ok:
            raise ValueError(f"org {scope_ref_id} not found")
    else:  # class
        ok = await conn.fetchval(
            "SELECT 1 FROM class_subject_teachers WHERE id = $1", scope_ref_id
        )
        if not ok:
            raise ValueError(f"cst {scope_ref_id} not found")

    await _ensure_no_existing_draft_for_scope(
        conn,
        scope=new_scope,
        scope_ref_id=scope_ref_id,
        curriculum_id=source["curriculum_id"],
        grade_id=source["grade_id"],
        subject_id=source["subject_id"],
    )

    async with conn.transaction():
        new_id = await conn.fetchval(
            """
            INSERT INTO breakdowns
              (scope, scope_ref_id, curriculum_id, grade_id, subject_id,
               book_id, parent_breakdown_id, total_teaching_days, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'draft')
            RETURNING id
            """,
            new_scope, scope_ref_id,
            source["curriculum_id"], source["grade_id"], source["subject_id"],
            source["book_id"], source["id"], source["total_teaching_days"],
        )

        # Deep-copy chapters → keep a map old_chapter_id → new_chapter_id
        chapter_rows = await conn.fetch(
            """
            SELECT id, book_chapter_id, position, teaching_days
            FROM breakdown_chapters
            WHERE breakdown_id = $1
            ORDER BY position
            """,
            source_id,
        )
        chapter_map: dict[UUID, UUID] = {}
        for ch in chapter_rows:
            new_ch = await conn.fetchval(
                """
                INSERT INTO breakdown_chapters
                  (breakdown_id, book_chapter_id, position, teaching_days)
                VALUES ($1, $2, $3, $4)
                RETURNING id
                """,
                new_id, ch["book_chapter_id"], ch["position"], ch["teaching_days"],
            )
            chapter_map[ch["id"]] = new_ch

        # Deep-copy slots → keep map old_slot_id → new_slot_id (for slot_topics)
        slot_rows = await conn.fetch(
            """
            SELECT id, breakdown_chapter_id, position, chapter_position,
                   slot_type, lp_type, topic_id, anchor_date
            FROM breakdown_slots
            WHERE breakdown_id = $1
            ORDER BY position
            """,
            source_id,
        )
        slot_map: dict[UUID, UUID] = {}
        for s in slot_rows:
            new_s = await conn.fetchval(
                """
                INSERT INTO breakdown_slots
                  (breakdown_id, breakdown_chapter_id, position, chapter_position,
                   slot_type, lp_type, topic_id, anchor_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                new_id, chapter_map[s["breakdown_chapter_id"]],
                s["position"], s["chapter_position"], s["slot_type"],
                s["lp_type"], s["topic_id"], s["anchor_date"],
            )
            slot_map[s["id"]] = new_s

        # Deep-copy slot_topics (assessment extras).
        if slot_map:
            extra_rows = await conn.fetch(
                """
                SELECT breakdown_slot_id, topic_id, position
                FROM breakdown_slot_topics
                WHERE breakdown_slot_id = ANY($1::uuid[])
                ORDER BY breakdown_slot_id, position
                """,
                list(slot_map.keys()),
            )
            for er in extra_rows:
                await conn.execute(
                    """
                    INSERT INTO breakdown_slot_topics (breakdown_slot_id, topic_id, position)
                    VALUES ($1, $2, $3)
                    """,
                    slot_map[er["breakdown_slot_id"]], er["topic_id"], er["position"],
                )

    log.info(
        "fork_breakdown: new=%s copied chapters=%d slots=%d",
        new_id, len(chapter_map), len(slot_map),
    )
    return new_id, len(chapter_map), len(slot_map)
