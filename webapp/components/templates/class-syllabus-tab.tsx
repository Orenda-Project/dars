/**
 * teacher-readonly-syllabus (Phase 2, F2.2) — Syllabus tab template.
 *
 * READ-ONLY path. The class teaching path is set by the school (org-decided,
 * D-1) and auto-seeded on the server (Phase 1). The teacher cannot add,
 * reorder, remove, or re-date chapters here.
 *
 * Each chapter row is now EXPANDABLE: clicking it reveals that chapter's
 * lessons + assessments in place (the unified rows formerly on the retired
 * Timeline tab). The per-chapter "Generate chapter plan" button stays in the
 * right rail for chapters that haven't been broken down yet.
 *
 * - Empty path → calm read-only message (D-7): the school hasn't published a
 *   syllabus for this class yet. NOT a picker.
 * - Non-empty  → the ordered path: each row shows the chapter number + title,
 *   position, date range as plain text, slot count, status badge; expanding it
 *   lists its lesson/assessment rows (view/generate LP + exam, mark-taught,
 *   skip). Chapters not yet broken down expand to a "generate a plan" hint.
 *
 * Pure template — data + callbacks as props, no fetching.
 */
"use client";

import type {
  ClassPathChapter,
  ClassPathChapterStatus,
  CstTimelineItem,
  SyllabusForCstResponse,
} from "@/lib/dars-api";
import {
  TimelineRow,
  type TimelineRowCallbacks,
} from "@/components/templates/class-timeline-tab";

interface SyllabusTabProps {
  data: SyllabusForCstResponse;
  /** Action 2: break a chapter down into slots. */
  onBreakDown: (book_chapter_id: string) => void;
  /** Set while a single chapter's break-down is in flight. */
  busyChapterId: string | null;

  /* ---- Expandable chapter contents (lessons + assessments) ---- */
  /** Unified timeline items for this CST; null while still loading. */
  timeline: CstTimelineItem[] | null;
  /** The single "you are here" slot id, if any. */
  currentSlotId: string | null;
  /** Which chapter is expanded (by book_chapter_id), or null. */
  expandedChapterId: string | null;
  /** Toggle a chapter open/closed. */
  onToggleChapter: (book_chapter_id: string) => void;
  /** Row callbacks (view/generate LP + exam, mark-taught, skip). */
  rowCallbacks: TimelineRowCallbacks;
  /** Slot whose LP is currently being generated/polled. */
  generatingSlotId: string | null;
  /** Assessment slot whose exam is currently being generated/polled. */
  generatingExamSlotId: string | null;
  /** Slot with an in-flight mark-taught/skip/complete. */
  busySlotId: string | null;
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
  const {
    data,
    onBreakDown,
    busyChapterId,
    timeline,
    currentSlotId,
    expandedChapterId,
    onToggleChapter,
    rowCallbacks,
    generatingSlotId,
    generatingExamSlotId,
    busySlotId,
  } = props;

  // Path is server-ordered by `position`; keep that order explicitly.
  const path = [...data.chapters].sort((a, b) => a.position - b.position);
  const isEmpty = path.length === 0;

  // The syllabus chapter is keyed by book_chapter_id; the timeline items carry
  // breakdown_chapter_position. Both derive from the same ordered class path,
  // so chapter `position` is the stable join key between the two.
  const itemsByPosition = new Map<number, CstTimelineItem[]>();
  for (const item of timeline ?? []) {
    const list = itemsByPosition.get(item.breakdown_chapter_position);
    if (list) list.push(item);
    else itemsByPosition.set(item.breakdown_chapter_position, [item]);
  }

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
          Your school sets this syllabus. Click a chapter to see its lessons and
          assessments, or generate a plan from any chapter below.
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
              expanded={expandedChapterId === ch.book_chapter_id}
              onToggle={() => onToggleChapter(ch.book_chapter_id)}
              items={itemsByPosition.get(ch.position) ?? []}
              timelineLoading={timeline === null}
              currentSlotId={currentSlotId}
              rowCallbacks={rowCallbacks}
              generatingSlotId={generatingSlotId}
              generatingExamSlotId={generatingExamSlotId}
              busySlotId={busySlotId}
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
/* F2.2 — an expandable chapter row in the path                        */
/* ------------------------------------------------------------------ */

function PathRow({
  ch,
  onBreakDown,
  breakingDown,
  expanded,
  onToggle,
  items,
  timelineLoading,
  currentSlotId,
  rowCallbacks,
  generatingSlotId,
  generatingExamSlotId,
  busySlotId,
}: {
  ch: ClassPathChapter;
  onBreakDown: (book_chapter_id: string) => void;
  breakingDown: boolean;
  expanded: boolean;
  onToggle: () => void;
  items: CstTimelineItem[];
  timelineLoading: boolean;
  currentSlotId: string | null;
  rowCallbacks: TimelineRowCallbacks;
  generatingSlotId: string | null;
  generatingExamSlotId: string | null;
  busySlotId: string | null;
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
    <li className={"rounded-md border bg-dars-parchment " + accent}>
      {isCurrent ? (
        <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
      ) : null}

      {/* Header — clicking anywhere here toggles the chapter open. */}
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={expanded}
        className="w-full text-left p-3 flex items-start gap-3"
      >
        {/* Disclosure caret */}
        <span
          className={
            "pt-0.5 text-dars-muted-light transition-transform " +
            (expanded ? "rotate-90" : "")
          }
          aria-hidden
        >
          ▸
        </span>

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

        {/* Right rail: generate the chapter plan. Stop propagation so the
            button doesn't also toggle the row. */}
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
              onClick={(e) => {
                e.stopPropagation();
                onBreakDown(ch.book_chapter_id);
              }}
              disabled={breakingDown}
              className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {breakingDown ? "Generating…" : "Generate chapter plan"}
            </button>
          )}
        </div>
      </button>

      {/* Expanded body — this chapter's lessons + assessments. */}
      {expanded ? (
        <div className="border-t border-dars-rule-light px-3 pb-3 pt-3">
          <ChapterContents
            brokenDown={brokenDown}
            items={items}
            timelineLoading={timelineLoading}
            currentSlotId={currentSlotId}
            rowCallbacks={rowCallbacks}
            generatingSlotId={generatingSlotId}
            generatingExamSlotId={generatingExamSlotId}
            busySlotId={busySlotId}
          />
        </div>
      ) : null}
    </li>
  );
}

/** The expanded contents of a chapter: its lesson + assessment rows. */
function ChapterContents({
  brokenDown,
  items,
  timelineLoading,
  currentSlotId,
  rowCallbacks,
  generatingSlotId,
  generatingExamSlotId,
  busySlotId,
}: {
  brokenDown: boolean;
  items: CstTimelineItem[];
  timelineLoading: boolean;
  currentSlotId: string | null;
  rowCallbacks: TimelineRowCallbacks;
  generatingSlotId: string | null;
  generatingExamSlotId: string | null;
  busySlotId: string | null;
}) {
  // Items win over the chapter's `is_generated` flag: the flag tracks whether
  // LPs were generated, NOT whether slots exist, so a freshly broken-down
  // chapter reads is_generated=false while already having a full set of
  // lesson/assessment slots. Render whatever slots the timeline carries; only
  // fall back to the hints when there's genuinely nothing to show.
  if (timelineLoading && items.length === 0) {
    return <p className="text-xs text-dars-muted">Loading lessons…</p>;
  }

  if (items.length === 0) {
    // No slots for this chapter. If it hasn't been broken down, nudge toward
    // the "Generate chapter plan" action in the header's right rail.
    return (
      <p className="text-xs text-dars-muted">
        {brokenDown
          ? "No lessons or assessments in this chapter yet."
          : "Generate a plan for this chapter to see its lessons and assessments."}
      </p>
    );
  }

  // Items arrive position-sorted from the endpoint; keep that order.
  const sorted = [...items].sort((a, b) => a.position - b.position);

  return (
    <ul className="space-y-2">
      {sorted.map((item) => (
        <li key={`${item.kind}-${item.id}`}>
          <TimelineRow
            item={item}
            isNow={item.id === currentSlotId}
            onViewLP={rowCallbacks.onViewLP}
            onViewExam={rowCallbacks.onViewExam}
            onMarkTaught={rowCallbacks.onMarkTaught}
            onSkip={rowCallbacks.onSkip}
            onGenerateLP={rowCallbacks.onGenerateLP}
            onGenerateExam={rowCallbacks.onGenerateExam}
            generating={generatingSlotId === item.id}
            generatingExam={generatingExamSlotId === item.id}
            busy={busySlotId === item.id}
          />
        </li>
      ))}
    </ul>
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
