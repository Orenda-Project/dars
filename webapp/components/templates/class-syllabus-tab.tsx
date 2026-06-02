/**
 * Phase 3 — Syllabus tab template.
 *
 * Planning entry point for a class: the published syllabus broken into
 * chapters with their date windows and computed slot counts. The teacher
 * can break a chapter down into lesson/assessment slots from here.
 *
 * Pure template: data + callbacks as props, no fetching.
 */
"use client";

import type { SyllabusForCstResponse } from "@/lib/dars-api";

interface SyllabusTabProps {
  data: SyllabusForCstResponse;
  onBreakDown: (book_chapter_id: string) => void;
  busyChapterId: string | null;
}

function formatDateRange(start: string | null, end: string | null): string {
  if (!start || !end) return "dates not set";
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    });
  return `${fmt(start)} → ${fmt(end)}`;
}

export function ClassSyllabusTab(props: SyllabusTabProps) {
  const { data, onBreakDown, busyChapterId } = props;

  const chapters = [...data.chapters].sort(
    (a, b) => a.chapter_number - b.chapter_number,
  );

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-semibold text-dars-ink">
          {data.periods_per_week} periods/week
        </span>
      </div>

      {data.syllabus_breakdown_id === null ? (
        <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
          <p className="text-sm font-medium text-dars-ink">No syllabus yet</p>
          <p className="text-xs text-dars-muted mt-1">
            No syllabus published for this class yet.
          </p>
        </div>
      ) : (
        <ol className="space-y-2">
          {chapters.map((ch) => {
            const isBusy = busyChapterId === ch.book_chapter_id;
            const accent = ch.is_current
              ? "relative border-dars-terra ring-1 ring-dars-terra/40"
              : "border-dars-rule-light";
            return (
              <li
                key={ch.book_chapter_id}
                className={
                  "rounded-md border bg-dars-parchment p-3 " + accent
                }
              >
                {ch.is_current ? (
                  <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
                ) : null}
                <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="text-sm font-semibold text-dars-ink truncate">
                        Ch {ch.chapter_number} · {ch.title}
                      </span>
                      {ch.is_current ? (
                        <span className="text-[10px] font-bold text-dars-terra uppercase tracking-wide">
                          Now
                        </span>
                      ) : null}
                    </div>
                    <div className="flex items-center gap-3 text-xs text-dars-muted">
                      <span className="font-mono text-dars-ink-soft">
                        {formatDateRange(ch.start_date, ch.end_date)}
                      </span>
                      {ch.slot_count > 0 ? (
                        <span>{ch.slot_count} periods</span>
                      ) : null}
                    </div>
                  </div>

                  <div className="shrink-0">
                    {ch.is_planned ? (
                      <span className="text-xs font-medium text-dars-muted">
                        Planned ✓
                      </span>
                    ) : ch.slot_count === 0 ? (
                      <span className="text-xs text-dars-muted-light">
                        Set dates first
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => onBreakDown(ch.book_chapter_id)}
                        disabled={isBusy}
                        className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
                      >
                        {isBusy ? "Generating…" : "Break it down"}
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
