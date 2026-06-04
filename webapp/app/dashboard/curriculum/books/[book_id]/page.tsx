/**
 * Book viewer — rendered tree + raw JSON (book-viewer F-1.3, F-1.4).
 *
 * One fetch (`getBookTree`) feeds both views, so they can't disagree (D-2):
 *  - Rendered: book metadata card → expandable chapters (linked SLOs +
 *    collapsible OCR text) → topics (topic_text + linked sub-SLOs).
 *  - Raw JSON: a collapsible block, default OFF (D-5), dumping the full tree.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import {
  books as booksApi,
  DarsApiError,
  type BookTree,
  type BookChapterTree,
} from "@/lib/dars-api";

export default function BookDetailPage() {
  const params = useParams<{ book_id: string }>();
  const bookId = params.book_id;
  const [tree, setTree] = useState<BookTree | null>(null);
  const [openChapters, setOpenChapters] = useState<Record<string, boolean>>({});
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await booksApi.getBookTree(bookId);
        if (cancelled) return;
        setTree({
          ...t,
          chapters: [...t.chapters].sort((a, b) => a.chapter_number - b.chapter_number),
        });
        setError(null);
      } catch (err) {
        if (!cancelled) setError(formatErr(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [bookId]);

  function toggleChapter(id: string) {
    setOpenChapters((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  async function copyJson() {
    if (!tree) return;
    try {
      await navigator.clipboard.writeText(JSON.stringify(tree, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard may be unavailable; silently ignore
    }
  }

  if (error && !tree) return <p className="text-sm text-dars-terra">{error}</p>;
  if (!tree) return <p className="text-sm text-dars-muted">Loading…</p>;

  return (
    <div>
      <div className="text-xs text-dars-muted mb-2">
        <Link href="/dashboard/curriculum" className="hover:text-dars-terra">
          ← Back to curriculum
        </Link>
      </div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-3">
        {tree.title}
      </h1>

      {/* Metadata card */}
      <dl className="rounded border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 grid grid-cols-2 sm:grid-cols-4 gap-x-4 gap-y-2 text-xs">
        <Meta label="Publisher" value={tree.publisher} />
        <Meta label="Edition" value={tree.edition} />
        <Meta label="Published" value={tree.published_year} />
        <Meta label="Chapters" value={tree.total_chapters ?? tree.chapters.length} />
        {tree.pdf_url ? (
          <div className="col-span-2 sm:col-span-4">
            <dt className="text-dars-muted-light uppercase tracking-wide text-[10px]">PDF</dt>
            <dd>
              <a
                href={tree.pdf_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-dars-terra hover:underline break-all"
              >
                {tree.pdf_url}
              </a>
            </dd>
          </div>
        ) : null}
      </dl>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      {/* Rendered chapters */}
      <ul className="space-y-2">
        {tree.chapters.map((c) => (
          <ChapterRow
            key={c.id}
            chapter={c}
            open={!!openChapters[c.id]}
            onToggle={() => toggleChapter(c.id)}
          />
        ))}
      </ul>

      {/* Raw JSON — collapsible, default off (D-5) */}
      <details className="mt-6 rounded border border-dars-rule-light bg-dars-parchment-mid">
        <summary className="cursor-pointer select-none px-3 py-2 text-sm text-dars-ink flex items-center gap-2 hover:bg-dars-parchment-deep">
          <span className="font-medium">Raw JSON</span>
          <span className="text-[10px] text-dars-muted-light">
            full book tree, OCR included
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault();
              copyJson();
            }}
            className="ml-auto text-xs text-dars-terra hover:underline"
          >
            {copied ? "Copied" : "Copy"}
          </button>
        </summary>
        <pre className="border-t border-dars-rule-light p-3 text-[11px] leading-relaxed text-dars-ink-soft overflow-auto max-h-[32rem] font-mono">
          {JSON.stringify(tree, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function ChapterRow({
  chapter,
  open,
  onToggle,
}: {
  chapter: BookChapterTree;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <li className="rounded border border-dars-rule-light bg-dars-parchment-mid">
      <button
        type="button"
        onClick={onToggle}
        className="w-full p-3 text-left flex items-center gap-2 hover:bg-dars-parchment-deep"
      >
        <span className="font-mono text-xs text-dars-muted">Ch {chapter.chapter_number}</span>
        <span className="flex-1 text-sm text-dars-ink">{chapter.title}</span>
        {chapter.start_page != null && chapter.end_page != null ? (
          <span className="text-[10px] text-dars-muted-light font-mono">
            pp. {chapter.start_page}–{chapter.end_page}
          </span>
        ) : null}
        <span className="text-[10px] text-dars-muted">{open ? "▼" : "▶"}</span>
      </button>

      {open ? (
        <div className="border-t border-dars-rule-light">
          {/* Linked SLOs */}
          {chapter.slos.length > 0 ? (
            <div className="px-3 py-2 border-b border-dars-rule-light">
              <p className="text-[10px] uppercase tracking-wide text-dars-muted-light mb-1">
                SLOs
              </p>
              <ul className="space-y-1 text-xs">
                {chapter.slos.map((s) => (
                  <li key={s.id} className="flex gap-2">
                    <span className="font-mono text-dars-muted shrink-0">{s.code}</span>
                    <span className="text-dars-ink-soft">{s.statement}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {/* Chapter OCR text — collapsed by default (can be long) */}
          {chapter.chapter_text && chapter.chapter_text.length > 0 ? (
            <details className="px-3 py-2 border-b border-dars-rule-light">
              <summary className="cursor-pointer select-none text-[10px] uppercase tracking-wide text-dars-muted-light hover:text-dars-ink">
                Show text ({chapter.chapter_text.length} pages)
              </summary>
              <div className="mt-2 space-y-2 text-[11px] text-dars-ink-soft max-h-80 overflow-auto">
                {chapter.chapter_text.map((entry, i) => (
                  <p key={i} className="whitespace-pre-line">
                    {typeof entry.text === "string" ? entry.text : JSON.stringify(entry)}
                  </p>
                ))}
              </div>
            </details>
          ) : null}

          {/* Topics */}
          {chapter.topics.length > 0 ? (
            <ul className="divide-y divide-dars-rule-light text-xs">
              {chapter.topics.map((t) => (
                <li key={t.id} className="px-3 py-2">
                  <p className="text-dars-ink">
                    <span className="font-mono text-dars-muted">{t.topic_number}.</span>{" "}
                    {t.title}
                  </p>
                  {t.topic_text ? (
                    <p className="text-[11px] text-dars-muted-light whitespace-pre-line mt-1">
                      {t.topic_text}
                    </p>
                  ) : null}
                  {t.sub_slos.length > 0 ? (
                    <ul className="mt-1.5 space-y-0.5">
                      {t.sub_slos.map((ss) => (
                        <li key={ss.id} className="flex gap-2">
                          <span className="font-mono text-dars-muted shrink-0">{ss.code}</span>
                          <span className="text-dars-ink-soft">{ss.statement}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-2 text-xs text-dars-muted">No topics.</p>
          )}
        </div>
      ) : null}
    </li>
  );
}

function Meta({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div>
      <dt className="text-dars-muted-light uppercase tracking-wide text-[10px]">{label}</dt>
      <dd className="text-dars-ink">{value != null && value !== "" ? value : "—"}</dd>
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
