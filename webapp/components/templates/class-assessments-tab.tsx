/**
 * F4.7 — Assessments tab template.
 *
 * Pure layout. Page owns data + slide-over + (future) results-form
 * navigation.
 */
"use client";

import type { ClassAssessmentSlotListItem } from "@/lib/dars-api";

interface AssessmentsTabProps {
  items: ClassAssessmentSlotListItem[];
  onView: (slot: ClassAssessmentSlotListItem) => void;
}

export function ClassAssessmentsTab({ items, onView }: AssessmentsTabProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No assessments yet</p>
        <p className="text-xs text-dars-muted mt-1">
          When the breakdown is published with FA/SA slots they'll appear here.
        </p>
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {items.map((slot) => {
        const isFA = slot.assessment_type === "formative";
        const accent = isFA
          ? "border-rose-300 bg-rose-50"
          : "border-violet-300 bg-violet-50";
        const tag = isFA ? "FA" : "SA";
        return (
          <li key={slot.id} className={"rounded-md border p-3 " + accent}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-xs font-mono text-dars-muted">
                #{slot.position}
              </span>
              <span className="text-[10px] font-bold text-dars-ink uppercase tracking-wide">
                {tag}
              </span>
              <StatusBadge status={slot.status} />
              <span className="text-xs text-dars-muted-light ml-auto">
                Ch {slot.breakdown_chapter_position}: {slot.breakdown_chapter_title}
              </span>
            </div>

            <p className="text-sm text-dars-ink">
              {slot.topic_titles.length === 0 ? (
                <em className="text-dars-muted">No topics linked</em>
              ) : (
                slot.topic_titles.join(" · ")
              )}
            </p>

            <div className="flex flex-wrap gap-2 mt-2">
              <button
                type="button"
                onClick={() => onView(slot)}
                className="px-2.5 py-1 rounded bg-dars-ink text-dars-parchment text-xs font-semibold hover:opacity-90"
              >
                View Exam
              </button>
              <button
                type="button"
                disabled
                className="px-2.5 py-1 rounded border border-dars-rule-light text-xs text-dars-muted cursor-not-allowed"
                title="Mastery entry ships in F4.13"
              >
                Record Results (soon)
              </button>
              <ExamStatusPill status={slot.exam_status} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    scheduled: "bg-dars-parchment-deep text-dars-ink-soft",
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

function ExamStatusPill({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    READY: { label: "Exam ready", cls: "text-emerald-700" },
    PENDING: { label: "Exam queued", cls: "text-dars-muted" },
    IN_FLIGHT: { label: "Exam generating", cls: "text-dars-muted" },
    ERROR: { label: "Exam error", cls: "text-dars-terra" },
    not_generated: { label: "No exam", cls: "text-dars-muted-light" },
  };
  const entry = map[status] ?? { label: status, cls: "text-dars-muted" };
  return (
    <span className={"text-[10px] font-medium ml-auto self-center " + entry.cls}>● {entry.label}</span>
  );
}
