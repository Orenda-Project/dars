CREATE TABLE IF NOT EXISTS books (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    core_id         INTEGER NOT NULL,
    curriculum      TEXT NOT NULL,
    grade           INTEGER NOT NULL,
    subject         TEXT NOT NULL,
    title           TEXT NOT NULL,
    publisher       TEXT,
    edition         TEXT,
    published_year  INTEGER,
    total_chapters  INTEGER,
    pdf_url         TEXT,
    series          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (core_id, curriculum)
);

CREATE TABLE IF NOT EXISTS book_chapters (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    core_id         INTEGER NOT NULL UNIQUE,
    book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    chapter_number  INTEGER NOT NULL,
    start_page      INTEGER,
    end_page        INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_books_curriculum_grade_subject ON books (curriculum, grade, subject);
CREATE INDEX IF NOT EXISTS idx_book_chapters_book_id ON book_chapters (book_id);
