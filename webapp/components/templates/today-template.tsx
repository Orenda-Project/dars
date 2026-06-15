/**
 * F4.4 — /teacher-app/today template.
 *
 * Pure layout. Receives the resolved TodayResponse + the page's action
 * handlers as props. The page wires mark-taught / slide-over state.
 */
"use client";

import Link from "next/link";

import type {
  AssessmentSlotEntry,
  LessonSlotEntry,
  TodayEntry,
  TodayResponse,
} from "@/lib/dars-api";
import { LpContextHeader } from "@/components/molecules/lp-context-header";
import { lpTypeLabel } from "@/lib/lp-type-label";

interface TodayTemplateProps {
  today: TodayResponse | null;
  loading: boolean;
  error: string | null;
  onViewLP: (slot: LessonSlotEntry, ctx: TodayEntry) => void;
  onMarkTaught: (slot: LessonSlotEntry, ctx: TodayEntry) => void;
  onViewExam: (slot: AssessmentSlotEntry, ctx: TodayEntry) => void;
  busySlotId: string | null;
}

export function TodayTemplate(props: TodayTemplateProps) {
  const { today, loading, error, onViewLP, onMarkTaught, onViewExam, busySlotId } = props;

  if (loading && !today) {
    // The first load can take ~30s: the backend lazily breaks down the current
    // chapter so Today has lessons to show. Explain the wait instead of a bare
    // spinner so it doesn't read as a hang.
    return (
      <div className="rounded-lg border border-dars-rule-light bg-dars-parchment-mid p-6 text-center">
        <p className="text-sm font-semibold text-dars-ink">
          Preparing your lessons…
        </p>
        <p className="text-xs text-dars-muted mt-1">
          We&apos;re planning this chapter for you. This can take up to a
          minute the first time — it&apos;s instant after that.
        </p>
      </div>
    );
  }
  if (error) {
    return <ErrorBanner message={error} />;
  }
  if (!today || today.items.length === 0) {
    return (
      <EmptyState
        title="No classes assigned to you yet"
        body="Add a class from My classes, or reach out to your administrator."
      />
    );
  }

  // Onboarding nudge: any CST that's past day 5 with no taught history
  // suggests the teacher joined mid-year. Surface a per-CST link to the
  // wizard (D-12 / F4.12).
  const onboardingCandidates = today.items.filter(
    (e) => e.day_number !== null && e.day_number > 5 && !e.previous_taught,
  );

  return (
    <div>
      <div className="mb-5 flex items-baseline justify-between">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
          Today
        </h1>
        <span className="text-xs text-dars-muted font-mono">{today.as_of}</span>
      </div>

      {onboardingCandidates.length > 0 ? (
        <div className="mb-4 rounded-md border border-dars-terra/30 bg-dars-terra-light/15 p-3 text-sm">
          <p className="font-medium text-dars-ink">
            Joining this class mid-year?
          </p>
          <p className="text-xs text-dars-muted mt-1">
            We can mark earlier slots as <em>unknown</em> in your SLO coverage
            and start the calendar at where you are.
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {onboardingCandidates.map((entry) => (
              <li key={entry.cst_id}>
                <a
                  href={`/teacher-app/onboarding/${entry.cst_id}`}
                  className="inline-block px-2.5 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90"
                >
                  Set starting point — Grade {entry.grade_code} {entry.subject_code}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <ul className="space-y-4">
        {today.items.map((entry) => (
          <li key={entry.cst_id}>
            <CSTBlock
              entry={entry}
              onViewLP={onViewLP}
              onMarkTaught={onMarkTaught}
              onViewExam={onViewExam}
              busy={busySlotId}
            />
          </li>
        ))}
      </ul>
    </div>
  );
}

function CSTBlock({
  entry,
  onViewLP,
  onMarkTaught,
  onViewExam,
  busy,
}: {
  entry: TodayEntry;
  onViewLP: TodayTemplateProps["onViewLP"];
  onMarkTaught: TodayTemplateProps["onMarkTaught"];
  onViewExam: TodayTemplateProps["onViewExam"];
  busy: string | null;
}) {
  const chapter = entry.current_chapter;
  return (
    <div className="rounded-lg border border-dars-rule-light bg-dars-parchment-mid overflow-hidden">
      <header className="px-4 py-2 border-b border-dars-rule-light bg-dars-parchment flex items-baseline gap-3">
        <span className="text-sm font-semibold text-dars-ink">
          Grade {entry.grade_code} · {entry.subject_code}
        </span>
        {entry.day_number !== null ? (
          <span className="text-xs text-dars-muted font-mono">
            Day {entry.day_number}
          </span>
        ) : (
          <span className="text-xs text-dars-muted italic">No class today</span>
        )}
        {entry.is_conflict ? (
          <span className="text-xs text-dars-terra font-medium">
            ⚠ conflict
          </span>
        ) : null}
      </header>

      <div className="p-4">
        {/* "You're on Chapter 3: Phonics" — plain language for a low-tech
            teacher. Shown whenever the class has a path, even off a class day. */}
        {chapter ? (
          <div className="mb-4">
            <p className="text-[10px] uppercase tracking-wide text-dars-muted font-semibold">
              You&apos;re on
            </p>
            <h3 className="font-[var(--font-cormorant)] text-xl font-bold text-dars-ink">
              {chapter.chapter_number != null
                ? `Chapter ${chapter.chapter_number}`
                : "Chapter"}
              {chapter.title ? `: ${chapter.title}` : ""}
            </h3>
          </div>
        ) : (
          <p className="mb-4 text-sm font-medium text-dars-ink">
            You&apos;ve finished the course. 🎉
          </p>
        )}

        {/* Today's lesson — the main card with View / Mark as taught. */}
        <div className="mb-1">
          <p className="text-[10px] uppercase tracking-wide text-dars-terra font-semibold mb-1">
            Today&apos;s lesson
          </p>
          {entry.assessment_slot ? (
            <AssessmentCard
              slot={entry.assessment_slot}
              entry={entry}
              onView={onViewExam}
            />
          ) : entry.lesson_slot ? (
            <LessonCard
              slot={entry.lesson_slot}
              entry={entry}
              onViewLP={onViewLP}
              onMarkTaught={onMarkTaught}
              busy={busy === entry.lesson_slot.slot_id}
            />
          ) : (
            <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-4">
              <p className="text-sm font-medium text-dars-ink">
                No class scheduled today
              </p>
              <p className="text-xs text-dars-muted mt-1">
                Today is a holiday or a non-teaching day — here&apos;s where you
                are and what&apos;s coming up.
              </p>
            </div>
          )}
        </div>

        {/* Last lesson / Next lesson — bracket today so the teacher always
            sees where they are in the chapter. */}
        <PrevNextStrip entry={entry} />
      </div>
    </div>
  );
}

/** Plain-language prev/next pair shown under today's lesson. "Last lesson" is
 * the most recent taught slot; "Next lesson" is the upcoming slot + its date. */
function PrevNextStrip({ entry }: { entry: TodayEntry }) {
  const prev = entry.previous_taught;
  const next = entry.next_up;
  return (
    <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3">
      <PrevNextCell
        label="Last lesson"
        value={
          prev
            ? `Day ${prev.position}`
            : "Nothing taught yet"
        }
        sub={prev?.taught_on ? `Taught ${prev.taught_on}` : undefined}
      />
      <PrevNextCell
        label="Next lesson"
        value={next ? `Day ${next.position}` : "End of the course"}
        sub={
          next
            ? [
                lpTypeLabel(next.lp_type) ?? undefined,
                next.projected_date ? `on ${next.projected_date}` : undefined,
              ]
                .filter(Boolean)
                .join(" · ") || undefined
            : undefined
        }
      />
    </div>
  );
}

function PrevNextCell({
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

function LessonCard({
  slot,
  entry,
  onViewLP,
  onMarkTaught,
  busy,
}: {
  slot: LessonSlotEntry;
  entry: TodayEntry;
  onViewLP: TodayTemplateProps["onViewLP"];
  onMarkTaught: TodayTemplateProps["onMarkTaught"];
  busy: boolean;
}) {
  const chapter = entry.current_chapter;
  return (
    <div className="rounded-md border border-dars-terra-light/50 bg-dars-parchment p-4">
      <div className="mb-3">
        <div className="flex items-start justify-between gap-3">
          <LpContextHeader
            chapterNumber={chapter?.chapter_number}
            chapterTitle={chapter?.title}
            topicTitle={slot.topic_title}
            lpType={slot.lp_type}
            className="flex-1 min-w-0"
          />
          <StatusBadge status={slot.status} />
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onViewLP(slot, entry)}
          className="px-3 py-1.5 rounded-md bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90"
        >
          View LP
        </button>
        {slot.status === "planned" ? (
          <button
            type="button"
            onClick={() => onMarkTaught(slot, entry)}
            disabled={busy}
            className="px-3 py-1.5 rounded-md border border-dars-ink-soft text-dars-ink text-xs font-medium hover:bg-dars-parchment-deep disabled:opacity-50"
          >
            {busy ? "Saving…" : "Mark Taught"}
          </button>
        ) : null}
      </div>
    </div>
  );
}

function AssessmentCard({
  slot,
  entry,
  onView,
}: {
  slot: AssessmentSlotEntry;
  entry: TodayEntry;
  onView: TodayTemplateProps["onViewExam"];
}) {
  const isFA = slot.assessment_type === "formative";
  const accent = isFA
    ? "border-rose-300 bg-rose-50"
    : "border-violet-300 bg-violet-50";
  const tag = isFA ? "Formative assessment" : "Summative assessment";
  return (
    <div className={"rounded-md border p-4 " + accent}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div>
          <p className="text-xs uppercase tracking-wide font-semibold text-dars-ink">
            {tag}
          </p>
          <p className="text-sm text-dars-ink mt-1 font-mono">
            slot #{slot.position} · {slot.topic_ids.length} topic
            {slot.topic_ids.length === 1 ? "" : "s"}
          </p>
        </div>
        <StatusBadge status={slot.status} />
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onView(slot, entry)}
          className="px-3 py-1.5 rounded-md bg-dars-ink text-dars-parchment text-xs font-semibold hover:opacity-90"
        >
          View Exam
        </button>
        <Link
          href={`/teacher-app/classes/${entry.cst_id}/assessments/${slot.slot_id}/results`}
          className="px-3 py-1.5 rounded-md border border-dars-rule-dark text-dars-ink text-xs font-medium hover:bg-dars-parchment-deep"
        >
          Record Results
        </Link>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    planned: "bg-dars-parchment-deep text-dars-ink-soft",
    taught: "bg-emerald-100 text-emerald-800",
    skipped: "bg-amber-100 text-amber-800",
    scheduled: "bg-dars-parchment-deep text-dars-ink-soft",
    completed: "bg-emerald-100 text-emerald-800",
  };
  return (
    <span
      className={
        "px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase tracking-wide " +
        (map[status] ?? "bg-dars-parchment-deep text-dars-ink-soft")
      }
    >
      {status}
    </span>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
      <p className="text-sm font-medium text-dars-ink">{title}</p>
      <p className="text-xs text-dars-muted mt-1">{body}</p>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
      <p className="text-sm font-semibold text-dars-ink">Couldn’t load today.</p>
      <p className="text-xs text-dars-muted mt-1">{message}</p>
    </div>
  );
}
