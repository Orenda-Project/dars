/**
 * teacher-adjustable-syllabus (Phase 3 Revival, F3.4) — Syllabus tab template.
 *
 * The class teaching path is auto-seeded from the org's published breakdown
 * (D-10) and shown as a settled plan by default (VIEW mode: dates as plain
 * text, no controls). The teacher can flip into EDIT mode (D-13) to adjust the
 * path for THIS class only (D-1/D-9): re-date, reorder upcoming chapters,
 * remove yet-to-start un-generated chapters, and add a chapter.
 *
 * Each chapter row stays EXPANDABLE in BOTH modes: clicking it reveals that
 * chapter's lessons + assessments in place (view/generate LP + exam,
 * mark-taught, skip). The per-chapter "Generate chapter plan" button stays in
 * the right rail for chapters that haven't been broken down yet. Edit mode only
 * ADDS the path-mutation affordances — it never hides the slot rows.
 *
 * - Empty path → calm message (D-7) when there is no recommendation; when a
 *   recommendation exists (no auto-seed because no published breakdown), the
 *   add-a-chapter prompt lets the teacher start the path.
 * - Non-empty  → the ordered path: chapter number + title, position, date range
 *   (plain text in view; inputs in edit), slot count, status badge; reorder ▲▼
 *   + remove ✕ in edit; expanding lists its lesson/assessment rows.
 *
 * Pure template — data + callbacks as props, no fetching (webapp/CLAUDE.md).
 * The `editing` boolean is owned by the page (D-13) and passed in with
 * `onToggleEdit`; the template never holds it.
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

/** A book chapter the teacher may add to the path (the picker source). */
export interface BookChapterOption {
  book_chapter_id: string;
  chapter_number: number;
  title: string;
}

interface SyllabusTabProps {
  data: SyllabusForCstResponse;
  /** Action 2: break a chapter down into slots. */
  onBreakDown: (book_chapter_id: string) => void;
  /** Set while a single chapter's break-down is in flight. */
  busyChapterId: string | null;

  /* ---- Edit-syllabus mode (D-13) — owned by the page ---- */
  /** True when the tab is in edit mode (controls revealed). */
  editing: boolean;
  /** Flip between view and edit mode. */
  onToggleEdit: () => void;
  /** Pick a chapter into the path (add-a-chapter). */
  onPick: (book_chapter_id: string) => void;
  /** Set a path chapter's date range (one or both bounds). */
  onSetDates: (
    book_chapter_id: string,
    dates: { start_date?: string; end_date?: string },
  ) => void;
  /** Reorder the path to this exact book_chapter_id order. */
  onReorder: (book_chapter_ids: string[]) => void;
  /** Remove a yet-to-start, un-generated chapter from the path. */
  onRemove: (book_chapter_id: string) => void;
  /** Every book chapter (for the picker); null while still loading. */
  bookChapters: BookChapterOption[] | null;
  /** True while any path mutation (pick/date/reorder/remove) is in flight. */
  pathBusy: boolean;

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
    editing,
    onToggleEdit,
    onPick,
    onSetDates,
    onReorder,
    onRemove,
    bookChapters,
    pathBusy,
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
  const recommended = data.recommended_next;

  // The syllabus chapter is keyed by book_chapter_id; the timeline items carry
  // breakdown_chapter_position. Both derive from the same ordered class path,
  // so chapter `position` is the stable join key between the two.
  const itemsByPosition = new Map<number, CstTimelineItem[]>();
  for (const item of timeline ?? []) {
    const list = itemsByPosition.get(item.breakdown_chapter_position);
    if (list) list.push(item);
    else itemsByPosition.set(item.breakdown_chapter_position, [item]);
  }

  // Move a chapter one step up/down within the path and submit the new order
  // (D-6 lock is enforced server-side; the UI only offers handles on
  // yet_to_start rows). No-op at the ends.
  const orderIds = path.map((c) => c.book_chapter_id);
  function move(idx: number, delta: number) {
    const target = idx + delta;
    if (target < 0 || target >= orderIds.length) return;
    const next = [...orderIds];
    [next[idx], next[target]] = [next[target], next[idx]];
    onReorder(next);
  }

  return (
    <div className="space-y-4">
      <div className="space-y-1">
        <div className="flex items-baseline justify-between gap-2">
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
          {/* Edit-syllabus toggle (D-13). Hidden on a genuinely empty path
              with no recommendation — there's nothing to edit yet. */}
          {!isEmpty || recommended ? (
            <button
              type="button"
              onClick={onToggleEdit}
              className={
                "shrink-0 px-3 py-1 rounded text-xs font-semibold " +
                (editing
                  ? "bg-dars-ink text-dars-parchment hover:opacity-90"
                  : "border border-dars-rule-light text-dars-ink hover:bg-dars-parchment-deep")
              }
            >
              {editing ? "Done" : "Edit syllabus"}
            </button>
          ) : null}
        </div>
        <p className="text-xs text-dars-muted">
          {editing
            ? "Editing this class's syllabus — adjust dates, reorder upcoming chapters, or add/remove. Changes apply to this class only."
            : "Your school sets this syllabus. Click a chapter to see its lessons and assessments, or generate a plan from any chapter below."}
        </p>
      </div>

      {isEmpty && !recommended ? (
        <EmptyPathMessage />
      ) : (
        <>
          {!isEmpty ? (
            <ol className="space-y-2">
              {path.map((ch, idx) => (
                <PathRow
                  key={ch.book_chapter_id}
                  ch={ch}
                  onBreakDown={onBreakDown}
                  breakingDown={busyChapterId === ch.book_chapter_id}
                  editing={editing}
                  onSetDates={onSetDates}
                  onRemove={onRemove}
                  onMoveUp={() => move(idx, -1)}
                  onMoveDown={() => move(idx, +1)}
                  canMoveUp={idx > 0}
                  canMoveDown={idx < path.length - 1}
                  pathBusy={pathBusy}
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
          ) : null}

          {/* Add-a-chapter (D-13). Always shown in edit mode; on an empty path
              with a recommendation it's the only way to start the path. */}
          {editing || (isEmpty && recommended) ? (
            <AddChapterPanel
              recommended={recommended}
              bookChapters={bookChapters}
              pathBookChapterIds={new Set(orderIds)}
              onPick={onPick}
              pathBusy={pathBusy}
            />
          ) : null}
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* F3.4 — add-a-chapter affordance (edit mode, or empty-path start)    */
/* ------------------------------------------------------------------ */

function AddChapterPanel({
  recommended,
  bookChapters,
  pathBookChapterIds,
  onPick,
  pathBusy,
}: {
  recommended: SyllabusForCstResponse["recommended_next"];
  bookChapters: BookChapterOption[] | null;
  pathBookChapterIds: Set<string>;
  onPick: (book_chapter_id: string) => void;
  pathBusy: boolean;
}) {
  // Pickable = book chapters not already in the path.
  const pickable = (bookChapters ?? []).filter(
    (c) => !pathBookChapterIds.has(c.book_chapter_id),
  );

  return (
    <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-3 space-y-2">
      <p className="text-xs font-semibold text-dars-ink">Add a chapter</p>

      {recommended ? (
        <button
          type="button"
          onClick={() => onPick(recommended.book_chapter_id)}
          disabled={pathBusy}
          className="w-full text-left px-3 py-2 rounded border border-dars-terra/40 bg-dars-terra/10 text-xs text-dars-ink hover:bg-dars-terra/15 disabled:opacity-50"
        >
          <span className="font-semibold text-dars-terra">Suggested next:</span>{" "}
          Ch {recommended.chapter_number} — {recommended.title}
        </button>
      ) : null}

      {bookChapters === null ? (
        <p className="text-xs text-dars-muted">Loading chapters…</p>
      ) : pickable.length === 0 ? (
        <p className="text-xs text-dars-muted">
          Every chapter is already in this class&rsquo;s path.
        </p>
      ) : (
        <label className="block">
          <span className="sr-only">Pick a chapter to add</span>
          <select
            defaultValue=""
            disabled={pathBusy}
            onChange={(e) => {
              const id = e.target.value;
              if (id) onPick(id);
              e.target.value = "";
            }}
            className="w-full text-xs rounded border border-dars-rule-light bg-dars-parchment px-2 py-1.5 text-dars-ink disabled:opacity-50"
          >
            <option value="" disabled>
              Pick another chapter…
            </option>
            {pickable.map((c) => (
              <option key={c.book_chapter_id} value={c.book_chapter_id}>
                Ch {c.chapter_number} — {c.title}
              </option>
            ))}
          </select>
        </label>
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
  editing,
  onSetDates,
  onRemove,
  onMoveUp,
  onMoveDown,
  canMoveUp,
  canMoveDown,
  pathBusy,
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
  editing: boolean;
  onSetDates: (
    book_chapter_id: string,
    dates: { start_date?: string; end_date?: string },
  ) => void;
  onRemove: (book_chapter_id: string) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  canMoveUp: boolean;
  canMoveDown: boolean;
  pathBusy: boolean;
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

  // D-6 / D-11 locks: only a yet_to_start chapter may move; only a
  // yet_to_start AND un-generated chapter may be removed.
  const reorderable = ch.status === "yet_to_start";
  const removable = ch.status === "yet_to_start" && !ch.is_generated;

  const accent = isCurrent
    ? "relative border-dars-terra ring-1 ring-dars-terra/40"
    : "border-dars-rule-light";

  return (
    <li className={"rounded-md border bg-dars-parchment " + accent}>
      {isCurrent ? (
        <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
      ) : null}

      {/* Header. In view mode the whole strip toggles the row; in edit mode
          the toggle is the title region only, so the date inputs + controls
          stay interactive (no nested <button>). */}
      <div className="p-3 flex items-start gap-3">
        {/* Reorder ▲▼ — edit mode, yet_to_start only (D-6). */}
        {editing ? (
          <div className="flex flex-col items-center pt-0.5">
            {reorderable ? (
              <>
                <button
                  type="button"
                  onClick={onMoveUp}
                  disabled={!canMoveUp || pathBusy}
                  aria-label="Move chapter up"
                  className="text-dars-muted hover:text-dars-ink disabled:opacity-30 leading-none text-xs"
                >
                  ▲
                </button>
                <button
                  type="button"
                  onClick={onMoveDown}
                  disabled={!canMoveDown || pathBusy}
                  aria-label="Move chapter down"
                  className="text-dars-muted hover:text-dars-ink disabled:opacity-30 leading-none text-xs"
                >
                  ▼
                </button>
              </>
            ) : (
              <span
                className="text-dars-muted-light leading-none text-xs"
                title="Started chapters are locked in place"
                aria-hidden
              >
                🔒
              </span>
            )}
          </div>
        ) : null}

        {/* Title region — the disclosure toggle (works in both modes). */}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          className="flex-1 min-w-0 text-left flex items-start gap-3"
        >
          <span
            className={
              "pt-0.5 text-dars-muted-light transition-transform " +
              (expanded ? "rotate-90" : "")
            }
            aria-hidden
          >
            ▸
          </span>
          <span className="pt-0.5 text-xs font-mono text-dars-muted-light tabular-nums">
            {ch.position}.
          </span>
          <span className="flex-1 min-w-0">
            <span className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-sm font-semibold text-dars-ink truncate">
                Ch {ch.chapter_number} · {ch.title}
              </span>
              <StatusBadge status={ch.status} />
              {ch.slot_count > 0 ? (
                <span className="text-xs text-dars-muted">
                  {ch.slot_count} period{ch.slot_count === 1 ? "" : "s"}
                </span>
              ) : null}
            </span>

            {/* View-mode date range — plain text. */}
            {!editing ? (
              <span className="flex items-center gap-1 text-xs text-dars-ink-soft">
                <span className="font-mono">{formatDate(ch.start_date)}</span>
                <span className="text-dars-muted-light">→</span>
                <span className="font-mono">{formatDate(ch.end_date)}</span>
              </span>
            ) : null}
          </span>
        </button>

        {/* Right rail. Stop propagation on every control so nothing toggles. */}
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

          {/* Remove ✕ — edit mode; only a yet_to_start, un-generated chapter
              (D-11). Otherwise show the reason. */}
          {editing ? (
            removable ? (
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onRemove(ch.book_chapter_id);
                }}
                disabled={pathBusy}
                className="text-xs text-dars-terra hover:underline disabled:opacity-50"
              >
                ✕ Remove
              </button>
            ) : (
              <span
                className="text-[10px] text-dars-muted-light"
                title={
                  ch.is_generated
                    ? "This chapter has a generated plan; clear it before removing."
                    : "Started chapters can't be removed."
                }
              >
                Can&rsquo;t remove
              </span>
            )
          ) : null}
        </div>
      </div>

      {/* Edit-mode date inputs — a full-width strip under the header so they
          never nest inside the toggle button (D-13). onBlur persists only a
          changed bound; COALESCE on the server keeps the other one. */}
      {editing ? (
        <div className="px-3 pb-3 -mt-1 flex items-center gap-2 text-xs text-dars-ink-soft">
          <label className="flex items-center gap-1">
            <span className="sr-only">Start date</span>
            <input
              type="date"
              defaultValue={ch.start_date ?? ""}
              disabled={pathBusy}
              onClick={(e) => e.stopPropagation()}
              onBlur={(e) => {
                const v = e.target.value || undefined;
                if ((ch.start_date ?? undefined) !== v && v) {
                  onSetDates(ch.book_chapter_id, { start_date: v });
                }
              }}
              className="rounded border border-dars-rule-light bg-dars-parchment px-2 py-1 text-dars-ink disabled:opacity-50"
            />
          </label>
          <span className="text-dars-muted-light">→</span>
          <label className="flex items-center gap-1">
            <span className="sr-only">End date</span>
            <input
              type="date"
              defaultValue={ch.end_date ?? ""}
              disabled={pathBusy}
              onClick={(e) => e.stopPropagation()}
              onBlur={(e) => {
                const v = e.target.value || undefined;
                if ((ch.end_date ?? undefined) !== v && v) {
                  onSetDates(ch.book_chapter_id, { end_date: v });
                }
              }}
              className="rounded border border-dars-rule-light bg-dars-parchment px-2 py-1 text-dars-ink disabled:opacity-50"
            />
          </label>
        </div>
      ) : null}

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
