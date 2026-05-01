"use client";

import { useState, useEffect, useCallback } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return "";
  try {
    return JSON.parse(raw).api_key ?? "";
  } catch {
    return "";
  }
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface Book {
  id: string;
  core_id: string;
  curriculum: string;
  grade: string;
  subject: string;
  title: string;
  publisher: string;
  total_chapters: number;
}

interface Chapter {
  id: string;
  core_id: string;
  book_id: string;
  title: string;
  chapter_number: number;
  start_page: number | null;
  end_page: number | null;
}

interface Topic {
  id: string;
  chapter_id: string;
  topic_number: number;
  title: string;
  page_number: number | null;
  sub_slos: string[];
}

interface Slot {
  id: string;
  topic_id: string;
  day_number: number;
  scheduled_date: string | null;
  topic_subtopic: string;
}

// ── Column header ─────────────────────────────────────────────────────────────

function ColHeader({ label }: { label: string }) {
  return (
    <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest px-4 py-3 border-b border-dars-rule-light">
      {label}
    </p>
  );
}

// ── Empty state ───────────────────────────────────────────────────────────────

function EmptyState({ message }: { message: string }) {
  return (
    <p className="px-4 py-6 text-sm text-dars-muted">{message}</p>
  );
}

// ── Books column ──────────────────────────────────────────────────────────────

function BooksColumn({
  books,
  selectedId,
  onSelect,
}: {
  books: Book[];
  selectedId: string | null;
  onSelect: (book: Book) => void;
}) {
  return (
    <div className="flex flex-col">
      <ColHeader label="Books" />
      {books.length === 0 && <EmptyState message="No books found." />}
      <ul>
        {books.map((book) => {
          const active = selectedId === book.id;
          return (
            <li key={book.id}>
              <button
                type="button"
                onClick={() => onSelect(book)}
                className={`w-full text-left px-4 py-3 border-b border-dars-rule-light transition-colors cursor-pointer border-x-0 border-t-0 ${
                  active
                    ? "bg-dars-terra text-white"
                    : "bg-white hover:bg-dars-parchment text-dars-ink"
                }`}
              >
                <p className={`text-sm font-semibold leading-tight ${active ? "text-white" : "text-dars-ink"}`}>
                  {book.title}
                </p>
                <p className={`text-xs mt-0.5 ${active ? "text-white/80" : "text-dars-muted"}`}>
                  {book.curriculum} · Grade {book.grade} · {book.subject}
                </p>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Chapters column ───────────────────────────────────────────────────────────

function ChaptersColumn({
  chapters,
  selectedId,
  onSelect,
}: {
  chapters: Chapter[];
  selectedId: string | null;
  onSelect: (chapter: Chapter) => void;
}) {
  const sorted = [...chapters].sort((a, b) => a.chapter_number - b.chapter_number);
  return (
    <div className="flex flex-col">
      <ColHeader label="Chapters" />
      {sorted.length === 0 && <EmptyState message="Select a book to see chapters." />}
      <ul>
        {sorted.map((ch) => {
          const active = selectedId === ch.id;
          const pages =
            ch.start_page != null && ch.end_page != null
              ? `pp. ${ch.start_page}–${ch.end_page}`
              : null;
          return (
            <li key={ch.id}>
              <button
                type="button"
                onClick={() => onSelect(ch)}
                className={`w-full text-left px-4 py-3 border-b border-dars-rule-light transition-colors cursor-pointer border-x-0 border-t-0 ${
                  active
                    ? "bg-dars-terra text-white"
                    : "bg-white hover:bg-dars-parchment text-dars-ink"
                }`}
              >
                <div className="flex items-start gap-2">
                  <span
                    className={`text-xs font-bold shrink-0 w-5 pt-0.5 ${
                      active ? "text-white/80" : "text-dars-muted"
                    }`}
                  >
                    {ch.chapter_number}
                  </span>
                  <div className="min-w-0">
                    <p
                      className={`text-sm font-semibold leading-tight ${
                        active ? "text-white" : "text-dars-ink"
                      }`}
                    >
                      {ch.title}
                    </p>
                    {pages && (
                      <p
                        className={`text-xs mt-0.5 ${
                          active ? "text-white/80" : "text-dars-muted"
                        }`}
                      >
                        {pages}
                      </p>
                    )}
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Topics & Slots column ─────────────────────────────────────────────────────

function TopicSlotsColumn({
  topics,
  slots,
  chapterSelected,
}: {
  topics: Topic[];
  slots: Record<string, Slot[]>;
  chapterSelected: boolean;
}) {
  if (!chapterSelected) {
    return (
      <div className="flex flex-col">
        <ColHeader label="Topics & Slots" />
        <EmptyState message="Select a chapter to see topics." />
      </div>
    );
  }

  if (topics.length === 0) {
    return (
      <div className="flex flex-col">
        <ColHeader label="Topics & Slots" />
        <div className="px-4 py-6">
          <p className="text-sm text-dars-muted">
            No breakdown yet. Run the admin breakdown endpoint to generate topics for this chapter.
          </p>
        </div>
      </div>
    );
  }

  const sorted = [...topics].sort((a, b) => a.topic_number - b.topic_number);

  return (
    <div className="flex flex-col">
      <ColHeader label="Topics & Slots" />
      <ul>
        {sorted.map((topic) => {
          const topicSlots = slots[topic.id] ?? [];
          return (
            <li key={topic.id} className="border-b border-dars-rule-light last:border-0">
              <div className="px-4 py-3">
                <div className="flex items-start gap-2 mb-2">
                  <span className="text-xs font-bold text-dars-muted shrink-0 w-5 pt-0.5">
                    {topic.topic_number}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-dars-ink leading-tight">
                      {topic.title}
                    </p>
                    {topic.page_number != null && (
                      <p className="text-xs text-dars-muted mt-0.5">p. {topic.page_number}</p>
                    )}
                  </div>
                </div>

                {topicSlots.length > 0 && (
                  <ul className="ml-7 space-y-1">
                    {topicSlots.map((slot) => (
                      <li
                        key={slot.id}
                        className="flex items-start gap-2 bg-dars-parchment border border-dars-rule-light rounded-md px-2.5 py-1.5"
                      >
                        <span className="text-[10px] font-bold text-dars-muted shrink-0 pt-0.5 w-4">
                          D{slot.day_number}
                        </span>
                        <div className="min-w-0">
                          <p className="text-xs text-dars-ink leading-tight">
                            {slot.topic_subtopic}
                          </p>
                          {slot.scheduled_date && (
                            <p className="text-[10px] text-dars-muted mt-0.5">
                              {new Date(slot.scheduled_date + "T00:00:00").toLocaleDateString(
                                "en-PK",
                                { day: "numeric", month: "short", year: "numeric" }
                              )}
                            </p>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CurriculumPage() {
  const [books, setBooks] = useState<Book[]>([]);
  const [selectedBook, setSelectedBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  // slots keyed by topic_id
  const [slots, setSlots] = useState<Record<string, Slot[]>>({});

  // Load all books on mount
  useEffect(() => {
    const apiKey = getApiKey();
    fetch(`${API_URL}/api/v1/books`, {
      headers: { "X-API-Key": apiKey },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: { items: Book[] }) => setBooks(data.items ?? []))
      .catch(() => {});
  }, []);

  // Load chapters when a book is selected
  const handleSelectBook = useCallback((book: Book) => {
    setSelectedBook(book);
    setChapters([]);
    setSelectedChapter(null);
    setTopics([]);
    setSlots({});

    const apiKey = getApiKey();
    fetch(`${API_URL}/api/v1/books/${book.id}/chapters`, {
      headers: { "X-API-Key": apiKey },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: { items: Chapter[] }) => setChapters(data.items ?? []))
      .catch(() => {});
  }, []);

  // Load topics + slots when a chapter is selected
  const handleSelectChapter = useCallback(
    (chapter: Chapter) => {
      setSelectedChapter(chapter);
      setTopics([]);
      setSlots({});

      if (!selectedBook) return;
      const apiKey = getApiKey();

      fetch(
        `${API_URL}/api/v1/books/${selectedBook.id}/chapters/${chapter.id}/topics`,
        { headers: { "X-API-Key": apiKey } }
      )
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then(async (data: { items: Topic[] }) => {
          const fetchedTopics = data.items ?? [];
          setTopics(fetchedTopics);

          // Fetch slots for each topic in parallel
          const slotResults = await Promise.all(
            fetchedTopics.map((t) =>
              fetch(`${API_URL}/api/v1/topics/${t.id}/slots`, {
                headers: { "X-API-Key": apiKey },
              })
                .then((r) => (r.ok ? r.json() : Promise.resolve({ items: [] })))
                .then((d: { items: Slot[] }) => ({ topicId: t.id, slots: d.items ?? [] }))
                .catch(() => ({ topicId: t.id, slots: [] }))
            )
          );

          const slotMap: Record<string, Slot[]> = {};
          for (const { topicId, slots: s } of slotResults) {
            slotMap[topicId] = s;
          }
          setSlots(slotMap);
        })
        .catch(() => {});
    },
    [selectedBook]
  );

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="font-serif text-2xl font-bold text-dars-ink mb-6">Curriculum</h1>

      <div className="border border-dars-rule-light rounded-lg overflow-hidden grid grid-cols-3 divide-x divide-dars-rule-light bg-white min-h-[400px]">
        {/* Column 1 — Books */}
        <BooksColumn
          books={books}
          selectedId={selectedBook?.id ?? null}
          onSelect={handleSelectBook}
        />

        {/* Column 2 — Chapters */}
        <ChaptersColumn
          chapters={chapters}
          selectedId={selectedChapter?.id ?? null}
          onSelect={handleSelectChapter}
        />

        {/* Column 3 — Topics & Slots */}
        <TopicSlotsColumn
          topics={topics}
          slots={slots}
          chapterSelected={selectedChapter !== null}
        />
      </div>
    </div>
  );
}
