/**
 * Syllabus Breakdown editor — chapter date ranges only.
 *
 * The breakdown is a global, chapter→date-range plan. Each chapter has an
 * explicit start/end date; teaching days are derived from the range vs. the
 * academic calendar. Advisory, non-blocking warnings (overlap / gap / zero
 * teaching days) are shown inline. Draft breakdowns are editable; published
 * are read-only. Publish via the button at top.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  books as booksApi,
  syllabusBreakdowns as syllabusBreakdownsApi,
  curriculum as curriculumApi,
  DarsApiError,
  type BookChapter,
  type SyllabusBreakdownDetail,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

const CHAPTER_WARNING_LABELS: Record<string, string> = {
  overlap: "Overlaps next chapter",
  gap: "Gap before next chapter",
  zero_teaching_days: "No teaching days in range",
};

export default function SyllabusBreakdownEditorPage() {
  const params = useParams<{ breakdown_id: string }>();
  const breakdownId = params.breakdown_id;

  const [data, setData] = useState<SyllabusBreakdownDetail | null>(null);
  const [bookChaptersById, setBookChaptersById] = useState<Map<string, BookChapter>>(new Map());
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [bd, { items: gs }, { items: ss }] = await Promise.all([
        syllabusBreakdownsApi.getBreakdown(breakdownId),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setData(bd);
      setGrades(gs);
      setSubjects(ss);

      if (bd.book_id) {
        const { items: bcs } = await booksApi.getBookChapters(bd.book_id);
        setBookChaptersById(new Map(bcs.map((c) => [c.id, c])));
      }
    } catch (err) {
      setError(formatErr(err));
    }
  }, [breakdownId]);

  useEffect(() => {
    load();
  }, [load]);

  const subjectCode = useMemo(() => {
    if (!data) return "";
    return subjects.find((s) => s.id === data.subject_id)?.code ?? "";
  }, [data, subjects]);

  // Explicit per-chapter date range. Either bound may be patched alone.
  async function handleSetChapterDate(
    chapterId: string,
    field: "start_date" | "end_date",
    value: string,
  ) {
    if (!data || !value) return;
    setBusy(true);
    try {
      await syllabusBreakdownsApi.patchChapter(data.id, chapterId, { [field]: value });
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await syllabusBreakdownsApi.publish(data.id);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  // Map each chapter to its advisory warning types for inline display.
  const warningsByChapter = useMemo(() => {
    const out = new Map<string, Set<string>>();
    for (const w of data?.chapter_range_warnings ?? []) {
      for (const cid of w.chapter_ids) {
        const set = out.get(cid) ?? new Set<string>();
        set.add(w.type);
        out.set(cid, set);
      }
    }
    return out;
  }, [data]);

  if (!data) return <p className="text-sm text-dars-muted">Loading…</p>;

  const editable = data.status === "draft";

  return (
    <div>
      <div className="text-xs text-dars-muted mb-2">
        <Link href="/dashboard/syllabus-breakdowns" className="hover:text-dars-terra">
          ← All syllabus breakdowns
        </Link>
      </div>

      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
            Syllabus Breakdown
            <span className="text-base font-normal text-dars-muted ml-2">
              {grades.find((g) => g.id === data.grade_id)?.code ?? "—"} ·{" "}
              {subjectCode || "—"}
            </span>
          </h1>
          <p className="text-xs text-dars-muted mt-1">
            Status: <strong>{data.status}</strong>
          </p>
        </div>
        {data.status === "draft" ? (
          <button
            type="button"
            onClick={handlePublish}
            disabled={busy}
            className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "…" : "Publish"}
          </button>
        ) : null}
      </div>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-3">
        {[...data.chapters]
          .sort((a, b) => {
            // Order by explicit start_date when set; fall back to position.
            if (a.start_date && b.start_date) return a.start_date.localeCompare(b.start_date);
            if (a.start_date) return -1;
            if (b.start_date) return 1;
            return a.position - b.position;
          })
          .map((c) => {
            const book = bookChaptersById.get(c.book_chapter_id);
            const warnings = warningsByChapter.get(c.id);
            return (
              <li key={c.id} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid">
                <header className="p-3 flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-dars-ink">
                      Ch {c.position} · {book?.title ?? "—"}
                    </p>
                    <p className="text-[10px] text-dars-muted-light">
                      {c.derived_teaching_days != null ? (
                        <>{c.derived_teaching_days} teaching day{c.derived_teaching_days === 1 ? "" : "s"}</>
                      ) : (
                        <>No date range set</>
                      )}
                    </p>
                    {warnings && warnings.size > 0 ? (
                      <p className="mt-1 flex flex-wrap gap-1">
                        {[...warnings].map((w) => (
                          <span
                            key={w}
                            title={CHAPTER_WARNING_LABELS[w] ?? w}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-dars-terra/10 text-dars-terra border border-dars-terra/30"
                          >
                            {CHAPTER_WARNING_LABELS[w] ?? w}
                          </span>
                        ))}
                      </p>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-1 text-xs text-dars-ink-soft">
                    <input
                      type="date"
                      aria-label={`Chapter ${c.position} start date`}
                      defaultValue={c.start_date ?? ""}
                      disabled={!editable || busy}
                      onBlur={(e) => {
                        if (e.target.value && e.target.value !== c.start_date) {
                          void handleSetChapterDate(c.id, "start_date", e.target.value);
                        }
                      }}
                      className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono"
                    />
                    <span className="text-dars-muted-light">→</span>
                    <input
                      type="date"
                      aria-label={`Chapter ${c.position} end date`}
                      defaultValue={c.end_date ?? ""}
                      disabled={!editable || busy}
                      onBlur={(e) => {
                        if (e.target.value && e.target.value !== c.end_date) {
                          void handleSetChapterDate(c.id, "end_date", e.target.value);
                        }
                      }}
                      className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono"
                    />
                  </div>
                </header>
              </li>
            );
          })}
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
