-- migrations/20260606000000_class_lesson_slot_topics.sql
-- Maps one class lesson slot (LP unit) to N ordered topics, so an LP unit
-- can merge multiple book topics (intelligent-chapter-planner D-2/D-4).
-- Mirrors class_assessment_slot_topics. Additive only; class_lesson_slots
-- is unchanged (its topic_id stays the primary topic for back-compat).
CREATE TABLE IF NOT EXISTS class_lesson_slot_topics (
    class_lesson_slot_id UUID NOT NULL
        REFERENCES class_lesson_slots(id) ON DELETE CASCADE,
    topic_id             UUID NOT NULL
        REFERENCES topics(id),
    position             INT  NOT NULL,   -- order within the LP unit (1..N)
    PRIMARY KEY (class_lesson_slot_id, topic_id)
);

CREATE INDEX IF NOT EXISTS idx_class_lesson_slot_topics_slot
    ON class_lesson_slot_topics(class_lesson_slot_id);
