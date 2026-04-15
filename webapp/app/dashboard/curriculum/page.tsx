"use client";

import { useEffect, useState } from "react";
import { BookLoader } from "@/components/atoms";

interface Session {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
}

// --- Book browser types ---

interface SubSlo {
  id: string;
  code: string;
  statement: string;
  slo_code: string;
}

interface BookTopic {
  id: string;
  title: string;
  sequence: number;
  sub_slos: SubSlo[];
}

interface BookChapter {
  id: number;
  chapter_number: number;
  title: string;
  topics: BookTopic[];
}

interface Book {
  id: number;
  title: string;
  grade: number;
  subject: string;
  chapters: BookChapter[];
}

// --- Curriculum list types ---

interface CurriculumSummary {
  id: string;
  name: string;
  provider: string;
  grade: string;
  subject: string;
  academic_year: string;
  is_active: boolean;
}

export default function CurriculumPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const [session, setSession] = useState<Session | null>(null);

  // --- Book browser state ---
  const [books, setBooks] = useState<Book[]>([]);
  const [booksLoading, setBooksLoading] = useState(false);
  const [booksError, setBooksError] = useState<string | null>(null);
  const [expandedBooks, setExpandedBooks] = useState<Set<number>>(new Set());
  const [selectedTopic, setSelectedTopic] = useState<BookTopic | null>(null);

  // --- Curriculum list state ---
  const [curriculums, setCurriculums] = useState<CurriculumSummary[]>([]);
  const [curriculumsLoading, setCurriculumsLoading] = useState(false);
  const [curriculumsError, setCurriculumsError] = useState<string | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem("dars_session");
    if (!raw) {
      window.location.href = "/login";
      return;
    }
    setSession(JSON.parse(raw) as Session);
  }, []);

  useEffect(() => {
    if (!session) return;
    fetchBooks(session.api_key);
    fetchCurriculums(session.api_key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  function fetchBooks(apiKey: string) {
    setBooksLoading(true);
    setBooksError(null);
    fetch(`${apiBase}/api/v1/curriculum/books`, {
      headers: { "X-API-Key": apiKey },
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem("dars_session");
            window.location.href = "/login";
            return;
          }
          throw new Error("Failed to fetch books.");
        }
        const data = (await res.json()) as Book[];
        setBooks(data);
        setBooksLoading(false);
      })
      .catch((err: unknown) => {
        setBooksError(err instanceof Error ? err.message : "An unexpected error occurred.");
        setBooksLoading(false);
      });
  }

  function fetchCurriculums(apiKey: string) {
    setCurriculumsLoading(true);
    setCurriculumsError(null);
    fetch(`${apiBase}/api/v1/curriculum/curriculums`, {
      headers: { "X-API-Key": apiKey },
    })
      .then(async (res) => {
        if (!res.ok) throw new Error("Failed to fetch curriculums.");
        const data = (await res.json()) as CurriculumSummary[];
        setCurriculums(data);
        setCurriculumsLoading(false);
      })
      .catch((err: unknown) => {
        setCurriculumsError(err instanceof Error ? err.message : "An unexpected error occurred.");
        setCurriculumsLoading(false);
      });
  }

  function toggleBook(bookId: number) {
    setExpandedBooks((prev) => {
      const next = new Set(prev);
      if (next.has(bookId)) {
        next.delete(bookId);
      } else {
        next.add(bookId);
      }
      return next;
    });
  }

  return (
    <div className="p-8 max-w-6xl">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-serif font-bold text-dars-ink">Curriculum</h1>
        {session && (
          <p className="text-sm text-dars-muted mt-1">
            {session.name} &middot; {session.email}
          </p>
        )}
      </div>

      {/* Curriculum list */}
      <section className="mb-10">
        <h2 className="text-lg font-serif font-semibold text-dars-ink mb-4">Curriculums</h2>

        {curriculumsLoading && (
          <div className="flex justify-center items-center min-h-[110px]">
            <BookLoader />
          </div>
        )}
        {curriculumsError && (
          <p className="text-sm text-red-600 border border-red-200 rounded-md px-3 py-2 bg-red-50">
            {curriculumsError}
          </p>
        )}
        {!curriculumsLoading && !curriculumsError && curriculums.length === 0 && (
          <p className="text-sm text-dars-muted">No curriculums found.</p>
        )}
        {!curriculumsLoading && curriculums.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {curriculums.map((c) => (
              <a
                key={c.id}
                href={`/dashboard/curriculum/${c.id}`}
                className="block border border-dars-rule-light rounded-lg bg-dars-parchment p-5 hover:border-dars-terra/50 hover:shadow-sm transition-all no-underline"
              >
                <div className="flex items-start justify-between gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-dars-ink leading-snug">{c.name}</h3>
                  {c.is_active && (
                    <span className="shrink-0 inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-green-100 text-green-800">
                      Active
                    </span>
                  )}
                </div>
                <p className="text-xs text-dars-muted">{c.provider}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <span className="text-[11px] font-medium text-dars-muted bg-dars-rule-light px-2 py-0.5 rounded">
                    {c.grade}
                  </span>
                  <span className="text-[11px] font-medium text-dars-muted bg-dars-rule-light px-2 py-0.5 rounded">
                    {c.subject}
                  </span>
                  {c.academic_year && (
                    <span className="text-[11px] font-medium text-dars-muted bg-dars-rule-light px-2 py-0.5 rounded">
                      {c.academic_year}
                    </span>
                  )}
                </div>
              </a>
            ))}
          </div>
        )}
      </section>

      {/* Book browser + Topic detail */}
      <section>
        <h2 className="text-lg font-serif font-semibold text-dars-ink mb-4">Book Browser</h2>

        <div className="flex flex-col lg:flex-row gap-6">
          {/* Left panel — book browser */}
          <div className="lg:w-80 shrink-0">
            <div className="border border-dars-rule-light rounded-lg bg-dars-parchment overflow-hidden">
              <div className="px-4 py-3 border-b border-dars-rule-light">
                <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide">
                  Books
                </p>
              </div>

              {booksLoading && (
                <div className="flex justify-center items-center min-h-[110px]">
                  <BookLoader />
                </div>
              )}
              {booksError && (
                <p className="px-4 py-4 text-sm text-red-600">{booksError}</p>
              )}
              {!booksLoading && !booksError && books.length === 0 && (
                <p className="px-4 py-4 text-sm text-dars-muted">No books found.</p>
              )}

              {!booksLoading && books.length > 0 && (
                <ul className="divide-y divide-dars-rule-light">
                  {books.map((book) => {
                    const isExpanded = expandedBooks.has(book.id);
                    return (
                      <li key={book.id}>
                        <button
                          type="button"
                          onClick={() => toggleBook(book.id)}
                          className="w-full text-left px-4 py-3 flex items-center gap-2 hover:bg-dars-parchment-deep transition-colors cursor-pointer bg-transparent border-none"
                        >
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            className={`h-3.5 w-3.5 text-dars-muted shrink-0 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <polyline points="9 18 15 12 9 6" />
                          </svg>
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-dars-ink truncate">{book.title}</p>
                            <p className="text-xs text-dars-muted">
                              Grade {book.grade} &middot; {book.subject}
                            </p>
                          </div>
                        </button>

                        {isExpanded && (
                          <ul className="border-t border-dars-rule-light bg-white">
                            {book.chapters.map((chapter) => (
                              <li key={chapter.id}>
                                <div className="px-4 py-2 border-b border-dars-rule-light bg-dars-parchment/50">
                                  <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide">
                                    Ch {chapter.chapter_number}: {chapter.title}
                                  </p>
                                </div>
                                <ul>
                                  {chapter.topics.map((topic) => (
                                    <li key={topic.id}>
                                      <button
                                        type="button"
                                        onClick={() => setSelectedTopic(topic)}
                                        className={`w-full text-left px-6 py-2 text-sm transition-colors cursor-pointer bg-transparent border-none ${
                                          selectedTopic?.id === topic.id
                                            ? "bg-dars-terra/10 text-dars-terra font-medium"
                                            : "text-dars-ink hover:bg-dars-parchment"
                                        }`}
                                      >
                                        {topic.sequence}. {topic.title}
                                      </button>
                                    </li>
                                  ))}
                                </ul>
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>

          {/* Right panel — topic detail */}
          <div className="flex-1 min-w-0">
            {!selectedTopic ? (
              <div className="border border-dars-rule-light rounded-lg bg-dars-parchment p-8 flex flex-col items-center justify-center text-center min-h-48">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-8 w-8 text-dars-muted/40 mb-3"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                  <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                </svg>
                <p className="text-sm text-dars-muted">
                  Select a topic from the book browser to see its details.
                </p>
              </div>
            ) : (
              <div className="border border-dars-rule-light rounded-lg bg-white overflow-hidden">
                <div className="px-5 py-4 border-b border-dars-rule-light bg-dars-parchment">
                  <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-0.5">
                    Topic
                  </p>
                  <h3 className="text-base font-serif font-semibold text-dars-ink">
                    {selectedTopic.title}
                  </h3>
                </div>

                <div className="px-5 py-5">
                  {selectedTopic.sub_slos.length === 0 ? (
                    <p className="text-sm text-dars-muted">No sub-SLOs linked to this topic.</p>
                  ) : (
                    <div className="space-y-3">
                      <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide">
                        Linked Sub-SLOs
                      </p>
                      {selectedTopic.sub_slos.map((sub) => (
                        <div
                          key={sub.id}
                          className="border border-dars-rule-light rounded-md p-4 bg-dars-parchment"
                        >
                          <div className="flex items-center gap-2 mb-1.5">
                            <span className="text-xs font-semibold font-mono text-dars-terra">
                              {sub.code}
                            </span>
                            <span className="text-dars-rule-dark text-xs">|</span>
                            <span className="text-xs text-dars-muted">
                              SLO:{" "}
                              <span className="font-mono font-medium text-dars-ink">
                                {sub.slo_code}
                              </span>
                            </span>
                          </div>
                          <p className="text-sm text-dars-ink">{sub.statement}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
