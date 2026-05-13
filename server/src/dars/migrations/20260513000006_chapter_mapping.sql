CREATE TABLE IF NOT EXISTS curriculum_chapter_schedule (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  curriculum              TEXT NOT NULL REFERENCES curriculums(code),
  book_id                 UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  chapter_id              UUID NOT NULL REFERENCES book_chapters(id) ON DELETE CASCADE,
  suggested_teaching_days INT NOT NULL,
  suggested_position      INT NOT NULL,
  term                    TEXT,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (curriculum, chapter_id)
);
CREATE INDEX IF NOT EXISTS idx_ccs_curriculum ON curriculum_chapter_schedule(curriculum);
