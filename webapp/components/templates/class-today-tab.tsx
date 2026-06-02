/**
 * Today dashboard — default class view.
 *
 * A single-class overview: today's date, today's lesson/assessment work with
 * view + mark-taught actions, a Covered/Now/Next strip, and a sub-SLO coverage
 * meter. Pure layout — the page owns fetching, mark-taught, and slide-over.
 */
"use client";

export interface TodayWorkLesson {
  kind: "lesson";
  slotId: string;
  position: number;
  slotType: "lesson" | "revision";
  lpType: string | null;
  topicTitle: string | null;
  status: "planned" | "taught" | "skipped";
  lpStatus: string;
}

export interface TodayWorkAssessment {
  kind: "assessment";
  slotId: string;
  position: number;
  assessmentType: "formative" | "summative";
  topicCount: number;
}

export type TodayWork = TodayWorkLesson | TodayWorkAssessment | null;

export interface ProgressSlot {
  position: number;
  topicTitle: string | null;
}

/** The syllabus chapter the class should be on today, when it has no
 * generated slots yet (so "break it down" hasn't run). */
export interface CurrentChapterToPlan {
  bookChapterId: string;
  chapterNumber: number;
  title: string;
}

export interface ClassTodayTabProps {
  /** Long-form date string, e.g. "Monday, 1 June 2026". */
  todayLabel: string;
  work: TodayWork;
  coveredCount: number;
  nowSlot: ProgressSlot | null;
  nextSlot: ProgressSlot | null;
  coverage: { taught: number; total: number } | null;
  busy: boolean;
  onViewLP: () => void;
  onMarkTaught: () => void;
  onViewExam: () => void;
  /** Set when today falls in a syllabus chapter that hasn't been broken down. */
  currentChapterToPlan?: CurrentChapterToPlan | null;
  onBreakDown?: (bookChapterId: string) => void;
}

export function ClassTodayTab({
  todayLabel,
  work,
  coveredCount,
  nowSlot,
  nextSlot,
  coverage,
  busy,
  onViewLP,
  onMarkTaught,
  onViewExam,
  currentChapterToPlan,
  onBreakDown,
}: ClassTodayTabProps) {
  return (
    <div className="space-y-5">
      <p className="text-xs uppercase tracking-wide text-dars-muted font-semibold">
        {todayLabel}
      </p>

      <TodayWorkCard
        work={work}
        busy={busy}
        onViewLP={onViewLP}
        onMarkTaught={onMarkTaught}
        onViewExam={onViewExam}
        nextSlot={nextSlot}
        currentChapterToPlan={currentChapterToPlan}
        onBreakDown={onBreakDown}
      />

      <ProgressStrip
        coveredCount={coveredCount}
        nowSlot={nowSlot}
        nextSlot={nextSlot}
      />

      {coverage && coverage.total > 0 ? (
        <CoverageMeter taught={coverage.taught} total={coverage.total} />
      ) : null}
    </div>
  );
}

function TodayWorkCard({
  work,
  busy,
  onViewLP,
  onMarkTaught,
  onViewExam,
  nextSlot,
  currentChapterToPlan,
  onBreakDown,
}: {
  work: TodayWork;
  busy: boolean;
  onViewLP: () => void;
  onMarkTaught: () => void;
  onViewExam: () => void;
  nextSlot: ProgressSlot | null;
  currentChapterToPlan?: CurrentChapterToPlan | null;
  onBreakDown?: (bookChapterId: string) => void;
}) {
  if (work === null) {
    // Distinguish "you're in a chapter you haven't planned yet" from "course over".
    if (currentChapterToPlan) {
      return (
        <div className="rounded-lg border border-dars-terra/40 bg-dars-terra/5 p-5">
          <p className="text-[10px] uppercase tracking-wide text-dars-terra font-semibold">
            You should be teaching
          </p>
          <h2 className="font-[var(--font-cormorant)] text-2xl font-bold text-dars-ink mt-1">
            Chapter {currentChapterToPlan.chapterNumber}: {currentChapterToPlan.title}
          </h2>
          <p className="text-sm text-dars-ink-soft mt-1">
            Break this chapter down to plan your lessons and see today&apos;s work.
          </p>
          <div className="mt-4">
            <button
              type="button"
              disabled={busy || !onBreakDown}
              onClick={() => onBreakDown?.(currentChapterToPlan.bookChapterId)}
              className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Breaking down…" : "Break it down"}
            </button>
          </div>
        </div>
      );
    }
    return (
      <div className="rounded-lg border border-dashed border-dars-rule-light bg-dars-parchment p-6">
        <p className="text-sm font-medium text-dars-ink">
          No class scheduled today
        </p>
        <p className="text-xs text-dars-muted mt-1">
          {nextSlot
            ? `Next up: Day ${nextSlot.position}${
                nextSlot.topicTitle ? ` · ${nextSlot.topicTitle}` : ""
              }.`
            : "You're at the end of the course."}
        </p>
      </div>
    );
  }

  if (work.kind === "assessment") {
    const label =
      work.assessmentType === "formative"
        ? "Formative assessment"
        : "Summative assessment";
    return (
      <div className="rounded-lg border border-dars-terra/40 bg-dars-terra/5 p-5">
        <p className="text-[10px] uppercase tracking-wide text-dars-terra font-semibold">
          Today · Day {work.position}
        </p>
        <h2 className="font-[var(--font-cormorant)] text-2xl font-bold text-dars-ink mt-1">
          {label}
        </h2>
        <p className="text-sm text-dars-ink-soft mt-1">
          {work.topicCount} topic{work.topicCount === 1 ? "" : "s"} covered
        </p>
        <div className="mt-4">
          <button
            type="button"
            onClick={onViewExam}
            className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90"
          >
            View exam
          </button>
        </div>
      </div>
    );
  }

  const isRevision = work.slotType === "revision";
  const taught = work.status === "taught";
  return (
    <div className="rounded-lg border border-dars-rule-dark bg-dars-parchment-mid p-5">
      <div className="flex items-center gap-2">
        <p className="text-[10px] uppercase tracking-wide text-dars-terra font-semibold">
          Today · Day {work.position}
        </p>
        {isRevision ? (
          <span className="text-[10px] font-semibold text-dars-terra uppercase tracking-wide">
            Revision
          </span>
        ) : null}
        <SlotStatusBadge status={work.status} />
      </div>
      <h2 className="font-[var(--font-cormorant)] text-2xl font-bold text-dars-ink mt-1">
        {work.topicTitle ?? "No topic"}
      </h2>
      <div className="mt-1 flex items-center gap-3">
        {work.lpType ? (
          <span className="text-xs text-dars-muted font-mono">{work.lpType}</span>
        ) : null}
        <LPStatusPill lp_status={work.lpStatus} />
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onViewLP}
          className="px-3 py-1.5 rounded border border-dars-rule-dark text-sm text-dars-ink hover:bg-dars-parchment-deep"
        >
          View lesson plan
        </button>
        {!taught ? (
          <button
            type="button"
            onClick={onMarkTaught}
            disabled={busy}
            className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "…" : "Mark as taught"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function ProgressStrip({
  coveredCount,
  nowSlot,
  nextSlot,
}: {
  coveredCount: number;
  nowSlot: ProgressSlot | null;
  nextSlot: ProgressSlot | null;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      <ProgressCell
        label="Covered"
        value={`${coveredCount} lesson${coveredCount === 1 ? "" : "s"} taught`}
      />
      <ProgressCell
        label="Now"
        value={
          nowSlot
            ? `Day ${nowSlot.position}`
            : "—"
        }
        sub={nowSlot?.topicTitle ?? undefined}
      />
      <ProgressCell
        label="Next"
        value={nextSlot ? `Day ${nextSlot.position}` : "End of course"}
        sub={nextSlot?.topicTitle ?? undefined}
      />
    </div>
  );
}

function ProgressCell({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment p-3">
      <p className="text-[10px] uppercase tracking-wide text-dars-muted font-semibold">
        {label}
      </p>
      <p className="text-sm font-semibold text-dars-ink mt-0.5">{value}</p>
      {sub ? (
        <p className="text-xs text-dars-muted truncate mt-0.5">{sub}</p>
      ) : null}
    </div>
  );
}

function CoverageMeter({ taught, total }: { taught: number; total: number }) {
  const pct = Math.round((taught / total) * 100);
  return (
    <div>
      <div className="flex items-baseline justify-between mb-1">
        <p className="text-[10px] uppercase tracking-wide text-dars-muted font-semibold">
          Sub-SLO coverage
        </p>
        <p className="text-xs text-dars-muted">
          {taught} / {total} · {pct}%
        </p>
      </div>
      <div className="h-2 rounded-full bg-dars-parchment-deep overflow-hidden">
        <div
          className="h-full bg-dars-terra rounded-full"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function SlotStatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    planned: "bg-dars-parchment-deep text-dars-ink-soft",
    taught: "bg-emerald-100 text-emerald-800",
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

function LPStatusPill({ lp_status }: { lp_status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    READY: { label: "LP ready", cls: "text-emerald-700" },
    PENDING: { label: "LP queued", cls: "text-dars-muted" },
    IN_FLIGHT: { label: "LP generating", cls: "text-dars-muted" },
    ERROR: { label: "LP error", cls: "text-dars-terra" },
    not_generated: { label: "No LP", cls: "text-dars-muted-light" },
  };
  const entry = map[lp_status] ?? { label: lp_status, cls: "text-dars-muted" };
  return (
    <span className={"text-xs font-medium " + entry.cls}>● {entry.label}</span>
  );
}
