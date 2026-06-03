/**
 * teacher-adjustable-syllabus (Phase 2, F2.1–F2.5) — Syllabus tab template.
 *
 * The teacher builds the class teaching PATH here: recommend → pick → date →
 * reorder → break down. The global default only *suggests* (D-1/D-3); the
 * class records its own real path (D-2). This is a pure template — data +
 * callbacks as props, no fetching.
 *
 * - Empty path  → recommendation prompt (F2.1): "Nothing planned yet…" with a
 *   button to pick the recommended chapter + a picker for any book chapter.
 * - Non-empty   → the ordered path (F2.2): each row has an editable date range,
 *   slot count, status badge (F2.5), Break-it-down (F2.4), reorder up/down
 *   (F2.3 — locked on started chapters, D-6) and remove (yet_to_start only).
 */
"use client";

import type {
  BookChapter,
  ClassPathChapter,
  ClassPathChapterStatus,
  SyllabusForCstResponse,
} from "@/lib/dars-api";

interface SyllabusTabProps {
  data: SyllabusForCstResponse;
  /**
   * Whole-book chapters so the teacher can pick ANY chapter, not just the
   * recommended one. `null` while loading; if it stays null (no book on the
   * CST) the tab still offers the recommended pick.
   */
  bookChapters: BookChapter[] | null;
  /** Action 1: add a chapter to the path. */
  onPick: (book_chapter_id: string) => void;
  /** D-7: set a path chapter's date range. */
  onSetDates: (
    book_chapter_id: string,
    body: { start_date?: string; end_date?: string },
  ) => void;
  /** D-6: reorder the path. `book_chapter_ids` is the full new order. */
  onReorder: (book_chapter_ids: string[]) => void;
  /** D-6: remove a yet_to_start chapter from the path. */
  onRemove: (book_chapter_id: string) => void;
  /** Action 2: break a dated chapter down into slots. */
  onBreakDown: (book_chapter_id: string) => void;
  /** Set while a single chapter's break-down is in flight. */
  busyChapterId: string | null;
  /** Set while any path mutation (pick/dates/reorder/remove) is in flight. */
  pathBusy: boolean;
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

export function ClassSyllabusTab(props: SyllabusTabProps) {
  const {
    data,
    bookChapters,
    onPick,
    onSetDates,
    onReorder,
    onRemove,
    onBreakDown,
    busyChapterId,
    pathBusy,
  } = props;

  // Path is server-ordered by `position`; keep that order explicitly.
  const path = [...data.chapters].sort((a, b) => a.position - b.position);
  const isEmpty = path.length === 0;

  // book_chapter_ids already in the path — used to filter the "pick any" list
  // so the teacher can't double-add a chapter.
  const pickedIds = new Set(path.map((c) => c.book_chapter_id));

  return (
    <div className="space-y-4">
      <div className="flex items-baseline gap-2">
        <span className="text-sm font-semibold text-dars-ink">
          {data.periods_per_week} periods/week
        </span>
        {!isEmpty ? (
          <span className="text-xs text-dars-muted">
            · {path.length} chapter{path.length === 1 ? "" : "s"} planned
          </span>
        ) : null}
      </div>

      {isEmpty ? (
        <EmptyPathPrompt
          data={data}
          bookChapters={bookChapters}
          pickedIds={pickedIds}
          onPick={onPick}
          pathBusy={pathBusy}
        />
      ) : (
        <>
          <ol className="space-y-2">
            {path.map((ch, idx) => (
              <PathRow
                key={ch.book_chapter_id}
                ch={ch}
                index={idx}
                path={path}
                onSetDates={onSetDates}
                onReorder={onReorder}
                onRemove={onRemove}
                onBreakDown={onBreakDown}
                breakingDown={busyChapterId === ch.book_chapter_id}
                pathBusy={pathBusy}
              />
            ))}
          </ol>

          <AddNextRow
            data={data}
            bookChapters={bookChapters}
            pickedIds={pickedIds}
            onPick={onPick}
            pathBusy={pathBusy}
          />
        </>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* F2.1 — empty-path recommendation prompt                             */
/* ------------------------------------------------------------------ */

function EmptyPathPrompt({
  data,
  bookChapters,
  pickedIds,
  onPick,
  pathBusy,
}: {
  data: SyllabusForCstResponse;
  bookChapters: BookChapter[] | null;
  pickedIds: Set<string>;
  onPick: (id: string) => void;
  pathBusy: boolean;
}) {
  const rec = data.recommended_next;

  return (
    <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center space-y-4">
      <div>
        <p className="text-sm font-medium text-dars-ink">Nothing planned yet.</p>
        <p className="text-xs text-dars-muted mt-1">
          {rec ? (
            <>
              The default syllabus suggests{" "}
              <span className="font-semibold text-dars-ink">
                Chapter {rec.chapter_number}: {rec.title}
              </span>{" "}
              — what would you like to teach?
            </>
          ) : (
            <>Pick a chapter from the book to start building this class&rsquo;s path.</>
          )}
        </p>
      </div>

      <div className="flex flex-col items-center gap-3">
        {rec ? (
          <button
            type="button"
            onClick={() => onPick(rec.book_chapter_id)}
            disabled={pathBusy}
            className="px-4 py-2 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {pathBusy ? "Adding…" : `Start with Chapter ${rec.chapter_number}`}
          </button>
        ) : null}

        <ChapterPicker
          bookChapters={bookChapters}
          pickedIds={pickedIds}
          onPick={onPick}
          disabled={pathBusy}
          label={rec ? "or pick another chapter" : "Pick a chapter"}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* F2.2/F2.3/F2.4/F2.5 — a chapter row in the path                     */
/* ------------------------------------------------------------------ */

function PathRow({
  ch,
  index,
  path,
  onSetDates,
  onReorder,
  onRemove,
  onBreakDown,
  breakingDown,
  pathBusy,
}: {
  ch: ClassPathChapter;
  index: number;
  path: ClassPathChapter[];
  onSetDates: SyllabusTabProps["onSetDates"];
  onReorder: SyllabusTabProps["onReorder"];
  onRemove: SyllabusTabProps["onRemove"];
  onBreakDown: SyllabusTabProps["onBreakDown"];
  breakingDown: boolean;
  pathBusy: boolean;
}) {
  const hasDates = Boolean(ch.start_date && ch.end_date);
  const isCurrent = ch.status === "in_progress";
  const isYetToStart = ch.status === "yet_to_start";
  // "Broken down" = the chapter actually has generated slots — NOT slot_count,
  // which is just the projected period count and is non-zero the moment dates
  // are set (that bug made every dated chapter look "Broken down ✓" and hid the
  // Generate button).
  const brokenDown = ch.is_generated;

  // D-6 reorder lock: only yet_to_start chapters move, and only into a slot
  // currently held by another yet_to_start chapter. Disabling a direction when
  // the neighbour is started guarantees we never submit an order that shifts a
  // started chapter (which the server would 422).
  const prev = path[index - 1];
  const next = path[index + 1];
  const canMoveUp =
    isYetToStart && index > 0 && prev?.status === "yet_to_start";
  const canMoveDown =
    isYetToStart && index < path.length - 1 && next?.status === "yet_to_start";

  function move(dir: -1 | 1) {
    const target = index + dir;
    const reordered = [...path];
    [reordered[index], reordered[target]] = [reordered[target], reordered[index]];
    onReorder(reordered.map((c) => c.book_chapter_id));
  }

  const accent = isCurrent
    ? "relative border-dars-terra ring-1 ring-dars-terra/40"
    : "border-dars-rule-light";

  return (
    <li className={"rounded-md border bg-dars-parchment p-3 " + accent}>
      {isCurrent ? (
        <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
      ) : null}

      <div className="flex items-start gap-3">
        {/* Reorder controls (D-6) */}
        <div className="flex flex-col gap-0.5 pt-0.5">
          <ReorderButton
            dir="up"
            disabled={!canMoveUp || pathBusy}
            onClick={() => move(-1)}
          />
          <ReorderButton
            dir="down"
            disabled={!canMoveDown || pathBusy}
            onClick={() => move(1)}
          />
        </div>

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

          {/* Date range (D-7) — dashboard's date-range pattern: patch on blur
              when the value actually changed. */}
          {/* Date range (D-7). Send BOTH dates together on every change so a
              partial save can never wipe the other end (the bug). Backend also
              COALESCEs, but sending both keeps the row internally consistent. */}
          <div className="flex items-center gap-1 text-xs text-dars-ink-soft">
            <input
              type="date"
              aria-label={`Chapter ${ch.chapter_number} start date`}
              defaultValue={ch.start_date ?? ""}
              disabled={pathBusy}
              onBlur={(e) => {
                const v = e.target.value || null;
                if (v !== ch.start_date) {
                  onSetDates(ch.book_chapter_id, {
                    start_date: v ?? undefined,
                    end_date: ch.end_date ?? undefined,
                  });
                }
              }}
              className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono disabled:opacity-50"
            />
            <span className="text-dars-muted-light">→</span>
            <input
              type="date"
              aria-label={`Chapter ${ch.chapter_number} end date`}
              defaultValue={ch.end_date ?? ""}
              disabled={pathBusy}
              onBlur={(e) => {
                const v = e.target.value || null;
                if (v !== ch.end_date) {
                  onSetDates(ch.book_chapter_id, {
                    start_date: ch.start_date ?? undefined,
                    end_date: v ?? undefined,
                  });
                }
              }}
              className="px-1.5 py-1 rounded border border-dars-rule-light bg-white text-xs font-mono disabled:opacity-50"
            />
          </div>
        </div>

        {/* Right rail: break-it-down + remove */}
        <div className="shrink-0 flex flex-col items-end gap-2">
          {brokenDown ? (
            <span className="text-xs font-medium text-dars-muted">Broken down ✓</span>
          ) : !hasDates ? (
            <span
              className="text-xs text-dars-muted-light"
              title="Set a start and end date before breaking this chapter down"
            >
              Set dates first
            </span>
          ) : (
            <button
              type="button"
              onClick={() => onBreakDown(ch.book_chapter_id)}
              disabled={breakingDown || pathBusy}
              className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {breakingDown ? "Generating…" : "Generate chapter plan"}
            </button>
          )}

          {isYetToStart ? (
            <button
              type="button"
              onClick={() => onRemove(ch.book_chapter_id)}
              disabled={pathBusy}
              aria-label={`Remove Chapter ${ch.chapter_number} from the path`}
              title="Remove from path"
              className="text-dars-muted-light hover:text-dars-terra text-sm leading-none disabled:opacity-50"
            >
              ✕
            </button>
          ) : null}
        </div>
      </div>
    </li>
  );
}

/* ------------------------------------------------------------------ */
/* F2.2 — "recommended next" append + pick-any (non-empty path)        */
/* ------------------------------------------------------------------ */

function AddNextRow({
  data,
  bookChapters,
  pickedIds,
  onPick,
  pathBusy,
}: {
  data: SyllabusForCstResponse;
  bookChapters: BookChapter[] | null;
  pickedIds: Set<string>;
  onPick: (id: string) => void;
  pathBusy: boolean;
}) {
  const rec = data.recommended_next;
  // The recommendation may already be in the path (server should exclude it,
  // but guard anyway); only offer it when it isn't.
  const showRec = rec && !pickedIds.has(rec.book_chapter_id);

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-md border border-dashed border-dars-rule-light bg-dars-parchment-mid p-3">
      {showRec ? (
        <button
          type="button"
          onClick={() => onPick(rec!.book_chapter_id)}
          disabled={pathBusy}
          className="px-3 py-1.5 rounded border border-dars-terra text-dars-terra text-xs font-semibold hover:bg-dars-terra/10 disabled:opacity-50"
        >
          {pathBusy
            ? "Adding…"
            : `+ Add next: Ch ${rec!.chapter_number} · ${rec!.title}`}
        </button>
      ) : null}

      <ChapterPicker
        bookChapters={bookChapters}
        pickedIds={pickedIds}
        onPick={onPick}
        disabled={pathBusy}
        label={showRec ? "or pick another chapter" : "Add a chapter"}
      />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Pick-any-chapter select                                             */
/* ------------------------------------------------------------------ */

function ChapterPicker({
  bookChapters,
  pickedIds,
  onPick,
  disabled,
  label,
}: {
  bookChapters: BookChapter[] | null;
  pickedIds: Set<string>;
  onPick: (id: string) => void;
  disabled: boolean;
  label: string;
}) {
  // No book wired (CST has no book_id) → can't offer "pick any". The
  // recommended pick (rendered by the caller) still works.
  if (bookChapters === null) return null;

  const available = [...bookChapters]
    .filter((bc) => !pickedIds.has(bc.id))
    .sort((a, b) => a.chapter_number - b.chapter_number);

  if (available.length === 0) {
    return (
      <span className="text-xs text-dars-muted-light">
        All book chapters are in the path.
      </span>
    );
  }

  return (
    <label className="flex items-center gap-2 text-xs text-dars-muted">
      <span>{label}</span>
      <select
        // value stays empty: it's an action picker, not a controlled field —
        // selecting fires onPick and resets.
        value=""
        disabled={disabled}
        onChange={(e) => {
          if (e.target.value) onPick(e.target.value);
        }}
        className="px-2 py-1 rounded border border-dars-rule-light bg-white text-xs text-dars-ink disabled:opacity-50"
      >
        <option value="">Choose a chapter…</option>
        {available.map((bc) => (
          <option key={bc.id} value={bc.id}>
            Ch {bc.chapter_number} · {bc.title}
          </option>
        ))}
      </select>
    </label>
  );
}

function ReorderButton({
  dir,
  disabled,
  onClick,
}: {
  dir: "up" | "down";
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={dir === "up" ? "Move chapter up" : "Move chapter down"}
      className="w-5 h-4 flex items-center justify-center rounded text-dars-muted hover:text-dars-ink hover:bg-dars-parchment-deep disabled:opacity-30 disabled:hover:bg-transparent text-[10px] leading-none"
    >
      {dir === "up" ? "▲" : "▼"}
    </button>
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
