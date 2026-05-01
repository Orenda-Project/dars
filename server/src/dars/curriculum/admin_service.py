"""
Admin service for curriculum breakdown.

Orchestrates the two-step AI pipeline (topic breakdown → day plan) and
persists the results into `topics` and `lesson_slots` tables.
"""
import logging
import uuid

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from dars.curriculum.breakdown_service import run_day_plan, run_topic_breakdown
from dars.curriculum.models import BookChapter, LessonSlot, Topic

log = logging.getLogger("curriculum.admin_service")


async def breakdown_chapter(db: AsyncSession, chapter_id: uuid.UUID) -> dict:
    """
    Run the full AI breakdown pipeline for a chapter and persist results.

    Steps:
    1. Load chapter_text + start_page from DB (raw SQL — not in ORM).
    2. Load the BookChapter for title.
    3. Run topic breakdown AI call.
    4. Run day plan AI call.
    5. Delete existing topics (cascades to lesson_slots) and insert fresh rows.
    6. Insert lesson slots per topic.
    7. Return summary {chapter_id, topics_count, slots_count}.
    """
    # 1. Load chapter_text via raw SQL (JSONB column not on ORM)
    result = await db.execute(
        text("SELECT chapter_text, start_page FROM book_chapters WHERE id = :id"),
        {"id": str(chapter_id)},
    )
    row = result.fetchone()
    if row is None:
        raise ValueError(f"Chapter not found: {chapter_id}")

    raw_chapter_text, start_page = row[0], row[1]

    # chapter_text may be stored as a JSONB dict {"text": "..."} or a plain string
    if isinstance(raw_chapter_text, dict):
        chapter_text: str = raw_chapter_text.get("text", "") or ""
    else:
        chapter_text = str(raw_chapter_text) if raw_chapter_text else ""

    if not chapter_text.strip():
        raise ValueError(f"Chapter {chapter_id} has no text content")

    # 2. Load BookChapter for title
    chapter = await db.get(BookChapter, chapter_id)
    if chapter is None:
        raise ValueError(f"Chapter not found: {chapter_id}")

    chapter_title = chapter.title

    log.info("Starting breakdown — chapter=%r id=%s", chapter_title, chapter_id)

    # 3. Topic breakdown
    topics_data = await run_topic_breakdown(
        chapter_title=chapter_title,
        chapter_text=chapter_text,
        start_page=start_page,
    )
    log.info("Topic breakdown returned %d topics", len(topics_data))

    # 4. Day plan
    slots_data = await run_day_plan(topics_data)
    log.info("Day plan returned %d slots", len(slots_data))

    # 5. Delete existing topics for this chapter (cascades to lesson_slots)
    await db.execute(delete(Topic).where(Topic.chapter_id == chapter_id))
    await db.flush()

    # 6. Insert new topics
    topic_objects: list[Topic] = []
    for td in topics_data:
        topic = Topic(
            chapter_id=chapter_id,
            topic_number=td["topic_number"],
            title=td["title"],
            page_number=td.get("page_number"),
            sub_slos=None,  # sub-SLO mapping is a separate step
        )
        db.add(topic)
        topic_objects.append(topic)

    # Flush to get DB-assigned ids
    await db.flush()

    # Store topic_text after flush using raw UPDATE (not in ORM)
    for topic_obj, td in zip(topic_objects, topics_data):
        topic_text = td.get("topic_text") or ""
        await db.execute(
            text("UPDATE topics SET topic_text = :txt WHERE id = :id"),
            {"txt": topic_text, "id": str(topic_obj.id)},
        )

    # 7. Insert lesson slots — slots reference topics by sequence (day_number maps
    #    to whatever topic the day-plan LLM assigned).  We do a best-effort
    #    assignment: all slots go on the first topic (since the day plan doesn't
    #    return which topic a slot belongs to explicitly when given the simplified
    #    format).  If there are multiple topics, assign slots round-robin by
    #    matching "Topic" strings in topic_subtopic against topic titles.
    total_slots = 0
    if topic_objects:
        # Build a lookup: title -> Topic (lowercased for fuzzy match)
        title_map = {t.title.lower(): t for t in topic_objects}
        # Fallback: first topic
        default_topic = topic_objects[0]

        for sd in slots_data:
            # Try to find a matching topic from the topic_subtopic string
            subtopic_str: str = sd["topic_subtopic"]
            matched_topic = default_topic
            for title_lower, topic_obj in title_map.items():
                if title_lower in subtopic_str.lower():
                    matched_topic = topic_obj
                    break

            slot = LessonSlot(
                topic_id=matched_topic.id,
                day_number=sd["day_number"],
                scheduled_date=sd.get("scheduled_date"),
                topic_subtopic=subtopic_str,
            )
            db.add(slot)
            total_slots += 1

    await db.commit()

    log.info(
        "Breakdown complete — chapter=%r topics=%d slots=%d",
        chapter_title,
        len(topic_objects),
        total_slots,
    )

    return {
        "chapter_id": str(chapter_id),
        "topics_count": len(topic_objects),
        "slots_count": total_slots,
    }
