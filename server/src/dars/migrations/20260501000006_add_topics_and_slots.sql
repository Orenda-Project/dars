-- Topics: one row per chapter topic extracted by the AI breakdown pipeline
CREATE TABLE topics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id      UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
    topic_number    INTEGER NOT NULL,
    title           TEXT NOT NULL,
    page_number     TEXT,
    topic_text      TEXT,
    sub_slos        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (chapter_id, topic_number)
);

-- Lesson slots: one row per teaching day produced by the day-plan step
CREATE TABLE lesson_slots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id        UUID NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    day_number      INTEGER NOT NULL,
    scheduled_date  DATE,
    topic_subtopic  TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (topic_id, day_number)
);
