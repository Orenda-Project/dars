/**
 * Syllabus tab template — teacher-adjustable-syllabus (Phase 3 Revival, F3.4)
 * reconciled with lp-context-header Phase 3 (D-12).
 *
 * The class teaching path is auto-seeded from the org's published breakdown
 * (D-10) and shown as a settled plan by default (VIEW mode: dates as plain
 * text, no controls). The teacher can flip into EDIT mode (D-13) to adjust the
 * path for THIS class only (D-1/D-9): re-date, reorder upcoming chapters,
 * remove yet-to-start un-generated chapters, and add a chapter.
 *
 * VIEW vs EDIT interaction (lp-context-header D-12):
 *   - VIEW  → each chapter row is a navigation Link to the dedicated Chapter
 *             Page (`/teacher-app/classes/{cstId}/chapters/{position}`), which
 *             shows that chapter's lessons + assessments. No inline accordion.
 *   - EDIT  → the row reveals path-mutation affordances (reorder ▲▼, date
 *             inputs, remove ✕) and does NOT navigate; "Add a chapter" shows.
 *   The per-chapter "Generate chapter plan" button stays in the right rail for
 *   chapters that haven't been broken down yet, in both modes.
 *
 * - Empty path → calm message (D-7) when there is no recommendation; when a
 *   recommendation exists, the add-a-chapter prompt lets the teacher start.
 * - Non-empty  → the ordered path: chapter number + title, position, date range
 *   (plain text in view; inputs in edit), slot count, status badge.
 *
 * Pure template — data + callbacks as props, no fetching (webapp/CLAUDE.md).
 * The `editing` boolean is owned by the page (D-13) and passed in with
 * `onToggleEdit`; the template never holds it.
 *
 * `ChapterContents`, `formatDate`, and `ChapterStatusBadge` are exported so the
 * dedicated Chapter Page reuses one renderer (lp-context-header D-11).
 */
"use client";

import Link from "next/link";

import type {
  ClassPathChapter,
  ClassPathChapterStatus,
  CstTimelineItem,
  Holiday,
  SyllabusForCstResponse,
} from "@/lib/dars-api";
import {
  computePlannerWarnings,
  type PlannerWarning,
} from "@/lib/planner-warnings";
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
  /** The CST whose syllabus this is — used to build chapter-page links. */
  cstId: string;
  /** Action 2: break a chapter down into slots. */
  onBreakDown: (book_chapter_id: string) => void;
  /** Set while a single chapter's break-down is in flight. */
  busyChapterId: string | null;
  /**
   * Chapter `position`s that already have lesson/assessment slots in the
   * timeline. Authoritative "a plan exists" signal — used to hide the
   * "Generate chapter plan" button even if the chapter's `is_generated` flag
   * lags (it's derived from slots joined on `book_chapter_id`, which can read
   * false while the timeline already carries the chapter's rows). Optional:
   * when the timeline hasn't loaded yet we fall back to `is_generated` alone.
   */
  generatedPositions?: Set<number>;

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

  /* ---- F1.1/F1.2 (D-3) — effective holidays for the inline range hint ---- */
  /** Effective non-teaching dates (ISO) for this CST. Empty when none/loading. */
  effectiveHolidays: Set<string>;
  /** Itemised holidays (names/sources) for the per-row tooltip. */
  holidayItems: Holiday[];
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
export function formatDate(iso: string | null): string {
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
    cstId,
    onBreakDown,
    busyChapterId,
    generatedPositions,
    editing,
    onToggleEdit,
    onPick,
    onSetDates,
    onReorder,
    onRemove,
    bookChapters,
    pathBusy,
    effectiveHolidays,
    holidayItems,
  } = props;

  // Path is server-ordered by `position`; keep that order explicitly.
  const path = [...data.chapters].sort((a, b) => a.position - b.position);
  const isEmpty = path.length === 0;
  const recommended = data.recommended_next;

  // F1.3 (D-4): advisory client-side warnings, recomputed from props on every
  // render so fixing dates clears them live (no stored state). Mirrors the
  // server's compute_range_warnings (overlap + zero-teaching); never blocks a
  // save. The per-row marker uses `warnedChapterIds` to flag offending rows.
  const warnings = computePlannerWarnings(data.chapters);
  const warnedChapterIds = new Set(warnings.flatMap((w) => w.chapterIds));

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
            : "Your school sets this syllabus. Open a chapter to see its lessons and assessments, or generate a plan from any chapter below."}
        </p>
      </div>

      {isEmpty && !recommended ? (
        <EmptyPathMessage />
      ) : (
        <>
          {/* F1.3 (D-4): advisory, non-blocking warning banner — soft Dars
              tokens, never red-error. Appears/updates as dates change. */}
          {warnings.length > 0 ? <PlannerWarningBanner warnings={warnings} /> : null}

          {!isEmpty ? (
            <ol className="space-y-2">
              {path.map((ch, idx) => (
                <PathRow
                  key={ch.book_chapter_id}
                  ch={ch}
                  cstId={cstId}
                  hasSlots={generatedPositions?.has(ch.position) ?? false}
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
                  effectiveHolidays={effectiveHolidays}
                  holidayItems={holidayItems}
                  warned={warnedChapterIds.has(ch.book_chapter_id)}
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
/* F1.3 (D-4) — advisory client-side warning banner (non-blocking).    */
/*   Soft Dars terra treatment — never hard red error styling. The      */
/*   message is tailored to which warning kinds are present.            */
/* ------------------------------------------------------------------ */

function PlannerWarningBanner({ warnings }: { warnings: PlannerWarning[] }) {
  const hasOverlap = warnings.some((w) => w.type === "overlap");
  const hasZero = warnings.some((w) => w.type === "zero_teaching_days");

  const parts: string[] = [];
  if (hasOverlap) parts.push("some chapters overlap — adjust the dates or reorder");
  if (hasZero)
    parts.push("a chapter's date range has no teaching periods — widen it or move past holidays");
  // Sentence-case the first clause, join the rest with "; also".
  const message = parts
    .map((p, i) => (i === 0 ? p.charAt(0).toUpperCase() + p.slice(1) : p))
    .join("; also ");

  return (
    <div
      role="status"
      className="rounded-md border border-dars-terra/30 bg-dars-terra/10 px-3 py-2 text-xs text-dars-terra"
    >
      <span aria-hidden>⚠ </span>
      {message}.
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
/* A chapter row in the path.                                          */
/*   VIEW → navigation Link to the Chapter Page (D-8/D-12).            */
/*   EDIT → re-date / reorder / remove controls; no navigation.        */
/* ------------------------------------------------------------------ */

function PathRow({
  ch,
  cstId,
  hasSlots,
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
  effectiveHolidays,
  holidayItems,
  warned,
}: {
  ch: ClassPathChapter;
  cstId: string;
  /** True when the timeline already carries slots for this chapter's position. */
  hasSlots: boolean;
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
  /** F1.2 (D-3): effective non-teaching dates for the in-range holiday hint. */
  effectiveHolidays: Set<string>;
  /** F1.2 (D-3): itemised holidays for the hover/focus tooltip. */
  holidayItems: Holiday[];
  /** F1.3 (D-4): true when this row is named in an advisory warning. */
  warned: boolean;
}) {
  const isCurrent = ch.status === "in_progress";
  // "Broken down" = the chapter actually has generated slots — NOT slot_count,
  // which is just the projected period count and is non-zero the moment dates
  // are set. `hasSlots` (timeline rows exist for this chapter) is the
  // authoritative signal and wins over `is_generated`, which can lag false
  // when slots exist but aren't joined on `book_chapter_id`. Either being true
  // means a plan exists → no "Generate chapter plan" button.
  const brokenDown = ch.is_generated || hasSlots;
  // slot_count is 0 when the chapter has no dated period capacity — generation
  // has nothing to size against, so the action is disabled with a reason.
  const noCapacity = ch.slot_count === 0;

  // D-6 / D-11 locks: only a yet_to_start chapter may move; only a
  // yet_to_start AND un-generated chapter may be removed.
  const reorderable = ch.status === "yet_to_start";
  const removable = ch.status === "yet_to_start" && !ch.is_generated;

  // F1.2 (D-3): effective holidays whose ISO date falls inside this chapter's
  // [start_date, end_date] (inclusive). String compare is valid for YYYY-MM-DD.
  // The hint explains the gap between the calendar span and the teaching span.
  const inRangeHolidays =
    ch.start_date && ch.end_date
      ? holidayItems
          .filter(
            (h) =>
              effectiveHolidays.has(h.date) &&
              h.date >= ch.start_date! &&
              h.date <= ch.end_date!,
          )
          .sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0))
      : [];
  const holidayCount = inRangeHolidays.length;
  // Tooltip: each in-range holiday's name (fall back to its date) + the date.
  const holidayTooltip = inRangeHolidays
    .map((h) => `${h.name ?? formatDate(h.date)} (${formatDate(h.date)})`)
    .join("\n");

  const accent = isCurrent
    ? "relative border-dars-terra ring-1 ring-dars-terra/40"
    : warned
      ? // F1.3 (D-4): subtle marker so the teacher finds the flagged row. Soft
        // terra ring, never a hard red error border.
        "relative border-dars-terra/40 ring-1 ring-dars-terra/30"
      : "border-dars-rule-light";

  const chapterHref = `/teacher-app/classes/${cstId}/chapters/${ch.position}`;

  // The title region: identical content in both modes, but in VIEW it's a
  // Link to the chapter page (D-12) and in EDIT it's plain (no navigation, so
  // the date inputs / controls below stay the focus).
  const titleInner = (
    <>
      <span className="pt-0.5 text-xs font-mono text-dars-muted-light tabular-nums">
        {ch.position}.
      </span>
      <span className="flex-1 min-w-0">
        <span className="flex items-center gap-2 mb-1.5 flex-wrap">
          <span className="text-sm font-semibold text-dars-ink truncate">
            Ch {ch.chapter_number} · {ch.title}
          </span>
          <ChapterStatusBadge status={ch.status} />
          {ch.slot_count > 0 ? (
            <span className="text-xs text-dars-muted">
              {ch.slot_count} period{ch.slot_count === 1 ? "" : "s"}
            </span>
          ) : null}
          {/* F1.2 (D-3): inline holiday-in-range hint, both VIEW and EDIT.
              Native title tooltip lists each in-range holiday + date. */}
          {holidayCount > 0 ? (
            <span
              className="text-xs text-dars-terra cursor-help"
              title={holidayTooltip}
              tabIndex={0}
            >
              🏖 {holidayCount} holiday{holidayCount === 1 ? "" : "s"} in range
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
    </>
  );

  return (
    <li className={"rounded-md border bg-dars-parchment " + accent}>
      {isCurrent ? (
        <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
      ) : null}

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

        {/* Title region. VIEW → Link to the chapter page (chevron points right,
            "open"); EDIT → plain, non-navigating. */}
        {editing ? (
          <div className="flex-1 min-w-0 flex items-start gap-3">
            <span className="pt-0.5 text-dars-muted-light text-xs" aria-hidden>
              ▸
            </span>
            {titleInner}
          </div>
        ) : (
          <Link
            href={chapterHref}
            aria-label={`Open chapter ${ch.chapter_number}: ${ch.title}`}
            className="flex-1 min-w-0 text-left flex items-start gap-3 group"
          >
            <span
              className="pt-0.5 text-dars-muted-light text-xs group-hover:text-dars-terra"
              aria-hidden
            >
              ›
            </span>
            {titleInner}
          </Link>
        )}

        {/* Right rail. */}
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

          {/* Remove ✕ — edit mode; only a yet_to_start, un-generated chapter
              (D-11). Otherwise show the reason. */}
          {editing ? (
            removable ? (
              <button
                type="button"
                onClick={() => onRemove(ch.book_chapter_id)}
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

      {/* Edit-mode date inputs — a full-width strip under the header. onBlur
          persists only a changed bound; COALESCE on the server keeps the
          other one. */}
      {editing ? (
        <div className="px-3 pb-3 -mt-1 flex items-center gap-2 text-xs text-dars-ink-soft">
          <label className="flex items-center gap-1">
            <span className="sr-only">Start date</span>
            <input
              type="date"
              defaultValue={ch.start_date ?? ""}
              disabled={pathBusy}
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
    </li>
  );
}

/** The contents of a chapter: its lesson + assessment rows. Rendered on the
 * dedicated Chapter Page (lp-context-header D-11). */
export function ChapterContents({
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
  // Render whatever slots the timeline carries; only fall back to the hints
  // when there's genuinely nothing to show. `is_generated` and "has slots" are
  // the same signal at the data level (is_generated = the chapter has class
  // slots), but the timeline is the authoritative source of the rows here, so
  // we key the body off `items` and use `brokenDown` only for the empty-state
  // copy.
  if (timelineLoading && items.length === 0) {
    return <p className="text-xs text-dars-muted">Loading lessons…</p>;
  }

  if (items.length === 0) {
    // No slots for this chapter. If it hasn't been broken down, nudge toward
    // the "Generate chapter plan" action.
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

export function ChapterStatusBadge({ status }: { status: ClassPathChapterStatus }) {
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
