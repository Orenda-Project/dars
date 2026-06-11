/**
 * Syllabus Breakdown editor — chapter date ranges only.
 *
 * The breakdown is a global, chapter→date-range plan. Each chapter has an
 * explicit start/end date; teaching days are derived from the range vs. the
 * academic calendar. Advisory, non-blocking warnings (overlap / gap / zero
 * teaching days) are shown inline. Both draft and published breakdowns are
 * editable (D-21): exam/holiday edits propagate live to class calendars by
 * design. Publishing (draft → published) is via the button at top.
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
  type BreakdownDateRange,
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

  // --- Exam periods + breakdown holidays (D-1/D-14). Both kinds share these
  // handlers; `kind` picks the matching API method. ---
  async function handleAddRange(
    kind: RangeKind,
    body: { start_date: string; end_date: string; name: string },
  ) {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      if (kind === "exam") await syllabusBreakdownsApi.addExamPeriod(data.id, body);
      else await syllabusBreakdownsApi.addHoliday(data.id, body);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleUpdateRange(
    kind: RangeKind,
    rangeId: string,
    body: { start_date?: string; end_date?: string; name?: string },
  ) {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      if (kind === "exam") await syllabusBreakdownsApi.updateExamPeriod(data.id, rangeId, body);
      else await syllabusBreakdownsApi.updateHoliday(data.id, rangeId, body);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteRange(kind: RangeKind, rangeId: string) {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      if (kind === "exam") await syllabusBreakdownsApi.deleteExamPeriod(data.id, rangeId);
      else await syllabusBreakdownsApi.deleteHoliday(data.id, rangeId);
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

  // Both draft and published breakdowns are editable (D-21, supersedes D-5):
  // exam/holiday edits propagate live to class calendars by design. The publish
  // button below stays draft-only (publish-once, then edit in place).
  const editable = data.status !== "deleted";

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

      <div className="grid gap-4 md:grid-cols-2 mb-6">
        <DateRangeSection
          title="Exam Periods"
          hint="Reserved exam windows. Excluded from teaching days everywhere."
          ranges={data.exam_periods}
          editable={editable}
          busy={busy}
          onAdd={(body) => handleAddRange("exam", body)}
          onUpdate={(id, body) => handleUpdateRange("exam", id, body)}
          onDelete={(id) => handleDeleteRange("exam", id)}
        />
        <DateRangeSection
          title="Holidays"
          hint="General non-teaching ranges (Eid, public holidays, breaks)."
          ranges={data.holidays}
          editable={editable}
          busy={busy}
          onAdd={(body) => handleAddRange("holiday", body)}
          onUpdate={(id, body) => handleUpdateRange("holiday", id, body)}
          onDelete={(id) => handleDeleteRange("holiday", id)}
        />
      </div>

      <h2 className="font-[var(--font-cormorant)] text-xl font-bold text-dars-ink mb-3">
        Chapters
      </h2>

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

type RangeKind = "exam" | "holiday";

/**
 * One labelled section (Exam Periods or Holidays): a list of named date ranges
 * with inline edit + delete, and an add row at the bottom. Editable on draft and
 * published breakdowns alike (`editable` is false only for deleted, D-21); edits
 * to a published breakdown propagate live to class calendars by design.
 * Pure presentational + local form state; all persistence is delegated to the
 * page via the on* callbacks.
 */
function DateRangeSection({
  title,
  hint,
  ranges,
  editable,
  busy,
  onAdd,
  onUpdate,
  onDelete,
}: {
  title: string;
  hint: string;
  ranges: BreakdownDateRange[];
  editable: boolean;
  busy: boolean;
  onAdd: (body: { start_date: string; end_date: string; name: string }) => void;
  onUpdate: (
    id: string,
    body: { start_date?: string; end_date?: string; name?: string },
  ) => void;
  onDelete: (id: string) => void;
}) {
  const [newName, setNewName] = useState("");
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");

  const canAdd = editable && !busy && newName.trim() && newStart && newEnd;

  function submitAdd() {
    if (!canAdd) return;
    onAdd({ start_date: newStart, end_date: newEnd, name: newName.trim() });
    setNewName("");
    setNewStart("");
    setNewEnd("");
  }

  const sorted = [...ranges].sort((a, b) => a.start_date.localeCompare(b.start_date));

  return (
    <section className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
      <h2 className="text-sm font-semibold text-dars-ink">{title}</h2>
      <p className="text-[10px] text-dars-muted-light mb-2">{hint}</p>

      {sorted.length === 0 ? (
        <p className="text-xs text-dars-muted mb-2">None set.</p>
      ) : (
        <ul className="space-y-2 mb-2">
          {sorted.map((r) => (
            <li
              key={r.id}
              className="rounded border border-dars-rule-light bg-white p-2 flex items-start justify-between gap-2"
            >
              <div className="min-w-0">
                <input
                  type="text"
                  aria-label={`${title} name`}
                  defaultValue={r.name}
                  disabled={!editable || busy}
                  onBlur={(e) => {
                    const v = e.target.value.trim();
                    if (v && v !== r.name) onUpdate(r.id, { name: v });
                  }}
                  className="w-full text-sm font-semibold text-dars-ink bg-transparent border-0 border-b border-transparent focus:border-dars-rule-light focus:outline-none disabled:cursor-default px-0"
                />
                <div className="mt-1 flex items-center gap-1 text-xs text-dars-ink-soft">
                  <input
                    type="date"
                    aria-label={`${title} ${r.name} start date`}
                    defaultValue={r.start_date}
                    disabled={!editable || busy}
                    onBlur={(e) => {
                      if (e.target.value && e.target.value !== r.start_date) {
                        onUpdate(r.id, { start_date: e.target.value });
                      }
                    }}
                    className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono"
                  />
                  <span className="text-dars-muted-light">→</span>
                  <input
                    type="date"
                    aria-label={`${title} ${r.name} end date`}
                    defaultValue={r.end_date}
                    disabled={!editable || busy}
                    onBlur={(e) => {
                      if (e.target.value && e.target.value !== r.end_date) {
                        onUpdate(r.id, { end_date: e.target.value });
                      }
                    }}
                    className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono"
                  />
                </div>
              </div>
              {editable ? (
                <button
                  type="button"
                  aria-label={`Delete ${r.name}`}
                  onClick={() => onDelete(r.id)}
                  disabled={busy}
                  className="text-[10px] px-1.5 py-0.5 rounded bg-dars-terra/10 text-dars-terra border border-dars-terra/30 hover:bg-dars-terra/20 disabled:opacity-50 shrink-0"
                >
                  Delete
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {editable ? (
        <div className="flex flex-wrap items-center gap-1 pt-2 border-t border-dars-rule-light">
          <input
            type="text"
            aria-label={`New ${title} name`}
            placeholder="Name"
            value={newName}
            disabled={busy}
            onChange={(e) => setNewName(e.target.value)}
            className="flex-1 min-w-[8rem] px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs"
          />
          <input
            type="date"
            aria-label={`New ${title} start date`}
            value={newStart}
            disabled={busy}
            onChange={(e) => setNewStart(e.target.value)}
            className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono"
          />
          <span className="text-dars-muted-light">→</span>
          <input
            type="date"
            aria-label={`New ${title} end date`}
            value={newEnd}
            disabled={busy}
            onChange={(e) => setNewEnd(e.target.value)}
            className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono"
          />
          <button
            type="button"
            onClick={submitAdd}
            disabled={!canAdd}
            className="px-2 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
          >
            Add
          </button>
        </div>
      ) : null}
    </section>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
