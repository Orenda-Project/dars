/**
 * class-timeline-view — dated lesson/assessment rows, grouped by chapter.
 *
 * The separate Timeline tab was retired (the Syllabus tab now expands each
 * chapter to reveal its rows in place). This file is kept as the home of the
 * shared row renderer (`TimelineRow`) + its prop contract (`TimelineRowProps`),
 * which the Syllabus tab reuses: lessons + assessments stamped with the
 * projector's date, "Now" marker, view/generate LP + exam, mark-taught/skip,
 * quiet generation pills, and inline conflict/overflow warnings.
 *
 * Pure layout — the page owns fetching + mark-taught/skip + slide-over.
 */
"use client";

import type { CstTimelineItem } from "@/lib/dars-api";
import { lpTypeLabel } from "@/lib/lp-type-label";

/** Callbacks + flags a single {@link TimelineRow} needs. The Syllabus tab
 *  threads these straight through from the page's timeline handlers. */
export interface TimelineRowCallbacks {
  onViewLP: (item: Extract<CstTimelineItem, { kind: "lesson" }>) => void;
  onViewExam: (item: Extract<CstTimelineItem, { kind: "assessment" }>) => void;
  onMarkTaught: (item: CstTimelineItem) => void;
  onSkip: (item: CstTimelineItem) => void;
  onGenerateLP: (item: Extract<CstTimelineItem, { kind: "lesson" }>) => void;
  onGenerateExam: (item: Extract<CstTimelineItem, { kind: "assessment" }>) => void;
}

export interface TimelineRowProps extends TimelineRowCallbacks {
  item: CstTimelineItem;
  isNow: boolean;
  generating: boolean;
  generatingExam: boolean;
  busy: boolean;
}

export function TimelineRow({
  item,
  isNow,
  onViewLP,
  onViewExam,
  onMarkTaught,
  onSkip,
  onGenerateLP,
  onGenerateExam,
  generating,
  generatingExam,
  busy,
}: TimelineRowProps) {
  const isAssessment = item.kind === "assessment";
  const accent = isNow
    ? "border-dars-terra ring-1 ring-dars-terra/40"
    : isAssessment
      ? item.assessment_type === "formative"
        ? "border-rose-300"
        : "border-violet-300"
      : "border-dars-rule-light";

  const bg = isAssessment
    ? item.assessment_type === "formative"
      ? "bg-rose-50"
      : "bg-violet-50"
    : "bg-dars-parchment-mid";

  return (
    <div
      ref={isNow ? scrollIntoView : undefined}
      className={`relative rounded-md border ${accent} ${bg} p-3`}
    >
      {isNow ? (
        <span className="absolute -left-px top-3 bottom-3 w-0.5 rounded bg-dars-terra" />
      ) : null}

      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <DateLabel item={item} />
            <span className="text-xs font-mono text-dars-muted">
              #{item.position}
            </span>
            {isNow ? (
              <span className="text-[10px] font-bold text-dars-terra uppercase tracking-wide">
                Now
              </span>
            ) : null}
            <KindTag item={item} />
            <StatusBadge status={item.status} />
          </div>
          <p className="text-sm text-dars-ink truncate">{topicText(item)}</p>
          <Flags item={item} />
        </div>

        <div className="flex flex-wrap gap-2 shrink-0 items-center">
          {item.kind === "lesson" ? (
            <>
              <LPAction
                item={item}
                generating={generating}
                onViewLP={() => onViewLP(item)}
                onGenerateLP={() => onGenerateLP(item)}
              />
              {item.status === "planned" ? (
                <ActionButtons
                  busy={busy}
                  onMarkTaught={() => onMarkTaught(item)}
                  onSkip={() => onSkip(item)}
                />
              ) : null}
              <GenPill kind="LP" status={item.lp_status} />
            </>
          ) : (
            <>
              <ExamAction
                item={item}
                generating={generatingExam}
                onViewExam={() => onViewExam(item)}
                onGenerateExam={() => onGenerateExam(item)}
              />
              {item.status === "scheduled" ? (
                <ActionButtons
                  busy={busy}
                  onMarkTaught={() => onMarkTaught(item)}
                  onSkip={() => onSkip(item)}
                  markLabel="Mark done"
                />
              ) : null}
              <GenPill kind="Exam" status={item.exam_status} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

/**
 * LP action for a lesson row. The button adapts to the LP's generation
 * state — there's nothing to "view" until an LP exists:
 *   - not_generated → "Generate LP" (the action this feature adds)
 *   - generating / PENDING / IN_FLIGHT → disabled "Generating…"
 *   - ERROR → "View LP" (shows the error in the slide-over) + "Retry"
 *   - READY (or any other) → "View LP"
 * The quiet GenPill still renders the status text alongside.
 */
function LPAction({
  item,
  generating,
  onViewLP,
  onGenerateLP,
}: {
  item: Extract<CstTimelineItem, { kind: "lesson" }>;
  generating: boolean;
  onViewLP: () => void;
  onGenerateLP: () => void;
}) {
  const inFlight =
    generating || item.lp_status === "PENDING" || item.lp_status === "IN_FLIGHT";

  if (inFlight) {
    return (
      <button
        type="button"
        disabled
        className="px-2.5 py-1 rounded border border-dars-rule-light text-xs text-dars-muted disabled:opacity-70"
      >
        Generating…
      </button>
    );
  }

  if (item.lp_status === "not_generated") {
    return (
      <button
        type="button"
        onClick={onGenerateLP}
        className="px-2.5 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90"
      >
        Generate LP
      </button>
    );
  }

  if (item.lp_status === "ERROR") {
    return (
      <>
        <button
          type="button"
          onClick={onViewLP}
          className="px-2.5 py-1 rounded border border-dars-rule-dark text-xs text-dars-ink hover:bg-dars-parchment-deep"
        >
          View LP
        </button>
        <button
          type="button"
          onClick={onGenerateLP}
          className="px-2.5 py-1 rounded border border-dars-terra text-xs font-semibold text-dars-terra hover:bg-dars-terra/10"
        >
          Retry
        </button>
      </>
    );
  }

  return (
    <button
      type="button"
      onClick={onViewLP}
      className="px-2.5 py-1 rounded border border-dars-rule-dark text-xs text-dars-ink hover:bg-dars-parchment-deep"
    >
      View LP
    </button>
  );
}

/**
 * Exam action for an assessment row (F-3.4) — the FA analogue of LPAction.
 * Adapts to the exam's generation state; there's nothing to "view" until an
 * exam exists:
 *   - not_generated → "Generate exam" (the action this feature adds)
 *   - generating / PENDING / IN_FLIGHT → disabled "Generating…"
 *   - ERROR → "View exam" (shows the error in the slide-over) + "Retry"
 *   - READY (or any other) → "View exam"
 * No per-slot config editor (D-10). The quiet GenPill still renders alongside.
 */
function ExamAction({
  item,
  generating,
  onViewExam,
  onGenerateExam,
}: {
  item: Extract<CstTimelineItem, { kind: "assessment" }>;
  generating: boolean;
  onViewExam: () => void;
  onGenerateExam: () => void;
}) {
  const inFlight =
    generating ||
    item.exam_status === "PENDING" ||
    item.exam_status === "IN_FLIGHT";

  if (inFlight) {
    return (
      <button
        type="button"
        disabled
        className="px-2.5 py-1 rounded border border-dars-rule-light text-xs text-dars-muted disabled:opacity-70"
      >
        Generating…
      </button>
    );
  }

  if (item.exam_status === "not_generated") {
    return (
      <button
        type="button"
        onClick={onGenerateExam}
        className="px-2.5 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90"
      >
        Generate exam
      </button>
    );
  }

  if (item.exam_status === "ERROR") {
    return (
      <>
        <button
          type="button"
          onClick={onViewExam}
          className="px-2.5 py-1 rounded border border-dars-rule-dark text-xs text-dars-ink hover:bg-dars-parchment-deep"
        >
          View exam
        </button>
        <button
          type="button"
          onClick={onGenerateExam}
          className="px-2.5 py-1 rounded border border-dars-terra text-xs font-semibold text-dars-terra hover:bg-dars-terra/10"
        >
          Retry
        </button>
      </>
    );
  }

  return (
    <button
      type="button"
      onClick={onViewExam}
      className="px-2.5 py-1 rounded bg-dars-ink text-dars-parchment text-xs font-semibold hover:opacity-90"
    >
      View exam
    </button>
  );
}

/** Imperative scroll so the "Now" row is visible on first paint. */
function scrollIntoView(el: HTMLDivElement | null) {
  if (el) {
    el.scrollIntoView({ block: "center", behavior: "auto" });
  }
}

function ActionButtons({
  busy,
  onMarkTaught,
  onSkip,
  markLabel = "Mark Taught",
}: {
  busy: boolean;
  onMarkTaught: () => void;
  onSkip: () => void;
  markLabel?: string;
}) {
  return (
    <>
      <button
        type="button"
        onClick={onMarkTaught}
        disabled={busy}
        className="px-2.5 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
      >
        {busy ? "…" : markLabel}
      </button>
      <button
        type="button"
        onClick={onSkip}
        disabled={busy}
        className="px-2.5 py-1 rounded border border-dars-rule-light text-xs text-dars-muted hover:bg-dars-parchment-deep disabled:opacity-50"
      >
        Skip
      </button>
    </>
  );
}

function DateLabel({ item }: { item: CstTimelineItem }) {
  if (!item.projected_date) {
    return <span className="text-xs font-semibold text-dars-muted-light">—</span>;
  }
  // Parse as local date (date-only ISO) to avoid TZ drift.
  const [y, m, d] = item.projected_date.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  const label = dt.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  return (
    <span className="text-xs font-semibold text-dars-ink">{label}</span>
  );
}

function KindTag({ item }: { item: CstTimelineItem }) {
  if (item.kind === "lesson") {
    if (item.slot_type === "revision") {
      return (
        <span className="text-[10px] font-semibold text-dars-terra uppercase tracking-wide">
          Revision
        </span>
      );
    }
    // lp-context-header F-2.6 / D-3: the LP type is the readable badge, no
    // longer a raw monospace enum.
    const typeLabel = lpTypeLabel(item.lp_type);
    return typeLabel ? (
      <span className="inline-flex items-center rounded-full bg-dars-terra px-2 py-0.5 text-[10px] font-semibold text-dars-parchment">
        {typeLabel}
      </span>
    ) : null;
  }
  const isFA = item.assessment_type === "formative";
  return (
    <span
      className={
        "text-[10px] font-bold uppercase tracking-wide " +
        (isFA ? "text-rose-700" : "text-violet-700")
      }
    >
      ◆ {isFA ? "FA" : "SA"}
    </span>
  );
}

function topicText(item: CstTimelineItem): React.ReactNode {
  if (item.kind === "lesson") {
    return item.topic_title ?? <em className="text-dars-muted">No topic</em>;
  }
  return item.topic_titles.length === 0 ? (
    <em className="text-dars-muted">No topics linked</em>
  ) : (
    item.topic_titles.join(" · ")
  );
}

function Flags({ item }: { item: CstTimelineItem }) {
  if (item.is_overflow) {
    return (
      <p className="text-[10px] text-amber-700 mt-0.5">
        Beyond year-end — no date
      </p>
    );
  }
  if (item.is_conflict) {
    return (
      <p className="text-[10px] text-amber-700 mt-0.5">
        Anchored to a non-teaching day
      </p>
    );
  }
  return null;
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    planned: "bg-dars-parchment-deep text-dars-ink-soft",
    scheduled: "bg-dars-parchment-deep text-dars-ink-soft",
    taught: "bg-emerald-100 text-emerald-800",
    completed: "bg-emerald-100 text-emerald-800",
    skipped: "bg-amber-100 text-amber-800",
  };
  return (
    <span
      className={
        "px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide " +
        (map[status] ?? "bg-dars-parchment-deep text-dars-ink-soft")
      }
    >
      {status}
    </span>
  );
}

/** Quiet generation signal (D-8): subordinate to date + topic. */
function GenPill({ kind, status }: { kind: "LP" | "Exam"; status: string }) {
  if (status === "not_generated") return null;
  const map: Record<string, { label: string; cls: string }> = {
    READY: { label: `${kind} ready`, cls: "text-emerald-600" },
    PENDING: { label: `${kind} queued`, cls: "text-dars-muted-light" },
    IN_FLIGHT: { label: `${kind} generating`, cls: "text-dars-muted-light" },
    ERROR: { label: `${kind} error`, cls: "text-dars-terra" },
  };
  const entry = map[status];
  if (!entry) return null;
  return (
    <span className={"text-[10px] font-medium self-center " + entry.cls}>
      ● {entry.label}
    </span>
  );
}
