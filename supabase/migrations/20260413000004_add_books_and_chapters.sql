CREATE TABLE books (
    id integer PRIMARY KEY,
    title text NOT NULL,
    grade integer NOT NULL,
    subject varchar(50) NOT NULL,
    curriculum varchar(20) NOT NULL,
    cover_image text,
    total_chapters integer,
    book_text jsonb,
    synced_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE book_chapters (
    id integer PRIMARY KEY,
    book_id integer NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    title text NOT NULL,
    chapter_number integer NOT NULL,
    start_page integer,
    end_page integer
);

CREATE INDEX idx_books_curriculum ON books(curriculum);
CREATE INDEX idx_books_grade ON books(grade);
CREATE INDEX idx_books_subject ON books(subject);
CREATE INDEX idx_book_chapters_book_id ON book_chapters(book_id);
