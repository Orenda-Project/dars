/**
 * All Books — every book in Dars, across all curriculum/grade/subject cells.
 *
 * The curriculum browser's Books tab is filtered by curriculum+grade+subject;
 * this is the unfiltered admin view so an imported book is findable without
 * guessing its cell. Grouped by curriculum → grade → subject; each row links to
 * the book viewer. Backend: GET /api/v2/books (no filter).
 */
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  books as booksApi,
  curriculum as curriculumApi,
  DarsApiError,
  type Book,
  type Curriculum,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

export default function AllBooksPage() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [curricula, setCurricula] = useState<Record<string, string>>({});
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [subjects, setSubjects] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [b, cs, gs, ss] = await Promise.all([
          booksApi.getBooks(),
          curriculumApi.getCurriculums(),
          curriculumApi.getGrades(),
          curriculumApi.getSubjects(),
        ]);
        if (cancelled) return;
        setBooks(b.items);
        setCurricula(Object.fromEntries(cs.items.map((c: Curriculum) => [c.id, c.code])));
        setGrades(Object.fromEntries(gs.items.map((g: Grade) => [g.id, g.display_name])));
        setSubjects(Object.fromEntries(ss.items.map((s: Subject) => [s.id, s.code])));
      } catch (err) {
        if (!cancelled) {
          setBooks([]);
          setError(formatErr(err));
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-1">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
          All books
        </h1>
        <Link
          href="/dashboard/admin/books"
          className="text-sm text-dars-terra hover:underline shrink-0"
        >
          Import a book →
        </Link>
      </div>
      <p className="text-sm text-dars-muted mb-4">
        Every book in Dars, across all curricula, grades, and subjects.
      </p>

      {error ? (
        <p className="text-sm text-dars-terra mb-3 rounded border border-dars-terra/30 bg-dars-terra/5 px-3 py-2">
          {error}
        </p>
      ) : null}

      {books === null ? (
        <p className="text-sm text-dars-muted">Loading…</p>
      ) : books.length === 0 ? (
        <p className="text-sm text-dars-muted">No books yet. Import one from core.</p>
      ) : (
        <>
          <p className="text-xs text-dars-muted-light mb-2">
            {books.length} book{books.length === 1 ? "" : "s"}
          </p>
          <ul className="space-y-1.5">
            {sortBooks(books, curricula, grades).map((b) => (
              <li key={b.id}>
                <Link
                  href={`/dashboard/curriculum/books/${b.id}`}
                  className="block rounded border border-dars-rule-light bg-dars-parchment-mid p-3 hover:bg-dars-parchment-deep"
                >
                  <div className="flex items-center gap-2">
                    <span className="flex-1 text-sm font-medium text-dars-ink">{b.title}</span>
                    {b.total_chapters != null ? (
                      <span className="text-[10px] text-dars-muted-light font-mono">
                        {b.total_chapters} ch
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[11px] text-dars-muted-light mt-0.5 flex flex-wrap gap-x-2">
                    <Tag>{curricula[b.curriculum_id] ?? "?"}</Tag>
                    <Tag>{grades[b.grade_id] ?? "?"}</Tag>
                    <Tag>{subjects[b.subject_id] ?? "?"}</Tag>
                    {b.publisher ? <span>· {b.publisher}</span> : null}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}

function sortBooks(
  books: Book[],
  curricula: Record<string, string>,
  grades: Record<string, string>,
): Book[] {
  return [...books].sort((a, b) => {
    const ca = curricula[a.curriculum_id] ?? "";
    const cb = curricula[b.curriculum_id] ?? "";
    if (ca !== cb) return ca.localeCompare(cb);
    const ga = grades[a.grade_id] ?? "";
    const gb = grades[b.grade_id] ?? "";
    if (ga !== gb) return ga.localeCompare(gb, undefined, { numeric: true });
    return a.title.localeCompare(b.title);
  });
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span className="font-mono text-dars-muted">{children}</span>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
