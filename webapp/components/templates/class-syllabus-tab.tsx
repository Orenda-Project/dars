/**
 * teacher-readonly-syllabus (Phase 2, F2.2) — Syllabus tab template.
 *
 * READ-ONLY. The class teaching path is set by the school (org-decided, D-1)
 * and auto-seeded on the server (Phase 1). The teacher cannot add, reorder,
 * remove, or re-date chapters here — the only action is generating a chapter
 * plan from the published path. This is a pure template — data + callbacks as
 * props, no fetching.
 *
 * - Empty path → calm read-only message (D-7): the school hasn't published a
 *   syllabus for this class yet. NOT a picker.
 * - Non-empty  → the ordered path: each row shows the chapter number + title,
 *   position, date range as plain text, slot count, status badge (F2.4 reuses
 *   existing styles), and the per-chapter "Generate chapter plan" button with
 *   its disabled/reason states.
 */
"use client";

import type {
  ClassPathChapter,
  ClassPathChapterStatus,
  SyllabusForCstResponse,
} from "@/lib/dars-api";

interface SyllabusTabProps {
  data: SyllabusForCstResponse;
  /** Action 2: break a chapter down into slots. The only action in this tab. */
  onBreakDown: (book_chapter_id: string) => void;
  /** Set while a single chapter's break-down is in flight. */
  busyChapterId: string | null;
}

const STATUS_LABEL: Record<ClassPathChapterStatus, string> = {
  yet_to_start: "Yet to start",
  in_progress: "In progress",
  done: "Done",
};

const STATUS_CLASS: Record<ClassPathChapterStatus, string> = {
  yet_to_start: "bg-dars-parchment-deep text-dars-ink-soft",
  in_progress: "bg-dars-terra/15 text-dars-terra",
  done: "bg-emerald-100 text-emerald-800",
};

/** ISO date (YYYY-MM-DD) → "12 Mar 2026" plain text, or "—" when unset. */
function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function ClassSyllabusTab(props: SyllabusTabProps) {
  const { data, onBreakDown, busyChapterId } = props;

  // Path is server-ordered by `position`; keep that order explicitly.
  const path = [...data.chapters].sort((a, b) => a.position - b.position);
  const isEmpty = path.length === 0;

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-semibold text-dars-ink">
            {data.periods_per_week} periods/week
          </span>
          {!isEmpty ? (
            <span className="text-xs text-dars-muted">
              · {path.length} chapter{path.length === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
        <p className="text-xs text-dars-muted">
          Your school sets this syllabus. Generate a plan from any chapter below.
        </p>
      </div>

      {isEmpty ? (
        <EmptyPathMessage />
      ) : (
        <ol className="space-y-2">
          {path.map((ch) => (
            <PathRow
              key={ch.book_chapter_id}
              ch={ch}
              onBreakDown={onBreakDown}
              breakingDown={busyChapterId === ch.book_chapter_id}
            />
          ))}
        </ol>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* D-7 — empty-path read-only message (no picker)                      */
/* ------------------------------------------------------------------ */

function EmptyPathMessage() {
  return (
    <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
      <p className="text-sm font-medium text-dars-ink">
        Your school hasn&rsquo;t published a syllabus for this class yet.
      </p>
      <p className="text-xs text-dars-muted mt-1">
        Once it does, the chapters will appear here and you can generate plans
        from them.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* F2.2 — a read-only chapter row in the path                          */
/* ------------------------------------------------------------------ */

function PathRow({
  ch,
  onBreakDown,
  breakingDown,
}: {
  ch: ClassPathChapter;
  onBreakDown: (book_chapter_id: string) => void;
  breakingDown: boolean;
}) {
  const isCurrent = ch.status === "in_progress";
  // "Broken down" = the chapter actually has generated slots — NOT slot_count,
  // which is just the projected period count and is non-zero the moment dates
  // are set.
  const brokenDown = ch.is_generated;
  // slot_count is 0 when the chapter has no dated period capacity — generation
  // has nothing to size against, so the action is disabled with a reason.
  const noCapacity = ch.slot_count === 0;

  const accent = isCurrent
    ? "relative border-dars-terra ring-1 ring-dars-terra/40"
    : "border-dars-rule-light";

  return (
    <li className={"rounded-md border bg-dars-parchment p-3 " + accent}>
      {isCurrent ? (
        <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
      ) : null}

      <div className="flex items-start gap-3">
        {/* Position (read-only, set by the school) */}
        <span className="pt-0.5 text-xs font-mono text-dars-muted-light tabular-nums">
          {ch.position}.
        </span>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <span className="text-sm font-semibold text-dars-ink truncate">
              Ch {ch.chapter_number} · {ch.title}
            </span>
            <StatusBadge status={ch.status} />
            {ch.slot_count > 0 ? (
              <span className="text-xs text-dars-muted">
                {ch.slot_count} period{ch.slot_count === 1 ? "" : "s"}
              </span>
            ) : null}
          </div>

          {/* Date range (D-7) — plain text, org-decided, not editable. */}
          <div className="flex items-center gap-1 text-xs text-dars-ink-soft">
            <span className="font-mono">{formatDate(ch.start_date)}</span>
            <span className="text-dars-muted-light">→</span>
            <span className="font-mono">{formatDate(ch.end_date)}</span>
          </div>
        </div>

        {/* Right rail: the only action — generate the chapter plan */}
        <div className="shrink-0 flex flex-col items-end gap-2">
          {brokenDown ? (
            <span className="text-xs font-medium text-dars-muted">Broken down ✓</span>
          ) : noCapacity ? (
            <span
              className="text-xs text-dars-muted-light"
              title="This chapter has no teaching periods in its date range yet"
            >
              No periods to plan
            </span>
          ) : (
            <button
              type="button"
              onClick={() => onBreakDown(ch.book_chapter_id)}
              disabled={breakingDown}
              className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {breakingDown ? "Generating…" : "Generate chapter plan"}
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

function StatusBadge({ status }: { status: ClassPathChapterStatus }) {
  return (
    <span
      className={
        "px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide " +
        STATUS_CLASS[status]
      }
    >
      {STATUS_LABEL[status]}
    </span>
  );
}
