/**
 * F5.9 — Book detail: chapters + topics.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  books as booksApi,
  DarsApiError,
  type Book,
  type BookChapter,
  type Topic,
} from "@/lib/dars-api";

export default function BookDetailPage() {
  const params = useParams<{ book_id: string }>();
  const bookId = params.book_id;
  const [book, setBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<BookChapter[]>([]);
  const [topicsByChapter, setTopicsByChapter] = useState<Record<string, Topic[]>>({});
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [b, { items: cs }] = await Promise.all([
        booksApi.getBook(bookId),
        booksApi.getBookChapters(bookId),
      ]);
      setBook(b);
      const sorted = [...cs].sort((a, b2) => a.chapter_number - b2.chapter_number);
      setChapters(sorted);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [bookId]);

  useEffect(() => {
    load();
  }, [load]);

  async function loadTopics(chapterId: string) {
    if (topicsByChapter[chapterId]) {
      const next = { ...topicsByChapter };
      delete next[chapterId];
      setTopicsByChapter(next);
      return;
    }
    try {
      const { items } = await booksApi.getTopics(chapterId);
      const sorted = [...items].sort((a, b) => a.topic_number - b.topic_number);
      setTopicsByChapter((prev) => ({ ...prev, [chapterId]: sorted }));
    } catch (err) {
      setError(formatErr(err));
    }
  }

  if (!book) return <p className="text-sm text-dars-muted">Loading…</p>;

  return (
    <div>
      <div className="text-xs text-dars-muted mb-2">
        <Link href="/dashboard/curriculum" className="hover:text-dars-terra">
          ← Back to curriculum
        </Link>
      </div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        {book.title}
      </h1>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-2">
        {chapters.map((c) => (
          <li key={c.id} className="rounded border border-dars-rule-light bg-dars-parchment-mid">
            <button
              type="button"
              onClick={() => loadTopics(c.id)}
              className="w-full p-3 text-left flex items-center gap-2 hover:bg-dars-parchment-deep"
            >
              <span className="font-mono text-xs text-dars-muted">Ch {c.chapter_number}</span>
              <span className="flex-1 text-sm text-dars-ink">{c.title}</span>
              <span className="text-[10px] text-dars-muted">
                {topicsByChapter[c.id] ? "▼" : "▶"}
              </span>
            </button>
            {topicsByChapter[c.id] ? (
              <ul className="border-t border-dars-rule-light divide-y divide-dars-rule-light text-xs">
                {topicsByChapter[c.id].map((t) => (
                  <li key={t.id} className="px-3 py-1.5">
                    <p className="text-dars-ink">
                      <span className="font-mono text-dars-muted">{t.topic_number}.</span>{" "}
                      {t.title}
                    </p>
                    {t.topic_text ? (
                      <p className="text-[11px] text-dars-muted-light whitespace-pre-line line-clamp-3 mt-1">
                        {t.topic_text}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
