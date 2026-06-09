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
          <div className="space-y-6">
            {groupBooks(books, grades, subjects).map((group) => (
              <section key={`${group.gradeLabel}|${group.subjectLabel}`}>
                <h2 className="text-sm font-semibold text-dars-ink mb-1.5 flex items-baseline gap-2 border-b border-dars-rule-light pb-1">
                  <span>{group.gradeLabel}</span>
                  <span className="text-dars-muted-light">·</span>
                  <span className="text-dars-muted">{group.subjectLabel}</span>
                  <span className="ml-auto text-[10px] font-normal text-dars-muted-light font-mono">
                    {group.books.length} book{group.books.length === 1 ? "" : "s"}
                  </span>
                </h2>
                <ul className="space-y-1.5">
                  {group.books.map((b) => (
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
                          {b.publisher ? <span>· {b.publisher}</span> : null}
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

type BookGroup = {
  gradeLabel: string;
  subjectLabel: string;
  books: Book[];
};

/** Bucket books by grade → subject, sorted grade-numeric then subject-alpha,
 * and books by title within each group. */
function groupBooks(
  books: Book[],
  grades: Record<string, string>,
  subjects: Record<string, string>,
): BookGroup[] {
  const byKey = new Map<string, BookGroup>();
  for (const b of books) {
    const gradeLabel = grades[b.grade_id] ?? "Unknown grade";
    const subjectLabel = subjects[b.subject_id] ?? "Unknown subject";
    const key = `${gradeLabel}|${subjectLabel}`;
    let group = byKey.get(key);
    if (!group) {
      group = { gradeLabel, subjectLabel, books: [] };
      byKey.set(key, group);
    }
    group.books.push(b);
  }
  const groups = [...byKey.values()];
  for (const g of groups) g.books.sort((a, b) => a.title.localeCompare(b.title));
  groups.sort((a, b) => {
    if (a.gradeLabel !== b.gradeLabel) {
      return a.gradeLabel.localeCompare(b.gradeLabel, undefined, { numeric: true });
    }
    return a.subjectLabel.localeCompare(b.subjectLabel);
  });
  return groups;
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
