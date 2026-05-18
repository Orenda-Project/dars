/**
 * F4.6 — Lessons tab template.
 *
 * Receives the resolved slot list grouped by chapter + handlers. The
 * page owns fetching + mark-taught/skip dispatch and slide-over state.
 */
"use client";

import type { ClassLessonSlotListItem } from "@/lib/dars-api";

export interface ChapterGroup {
  chapter_id: string;
  chapter_position: number;
  chapter_title: string;
  slots: ClassLessonSlotListItem[];
}

interface LessonsTabProps {
  groups: ChapterGroup[];
  onViewLP: (slot: ClassLessonSlotListItem) => void;
  onMarkTaught: (slot: ClassLessonSlotListItem) => void;
  onSkip: (slot: ClassLessonSlotListItem) => void;
  busySlotId: string | null;
}

export function ClassLessonsTab({
  groups,
  onViewLP,
  onMarkTaught,
  onSkip,
  busySlotId,
}: LessonsTabProps) {
  if (groups.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No lessons yet</p>
        <p className="text-xs text-dars-muted mt-1">
          Once a breakdown is published for this class, lesson slots will
          appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.chapter_id}>
          <h2 className="sticky top-[105px] z-10 bg-dars-parchment/95 backdrop-blur py-1 border-b border-dars-rule-light text-sm font-semibold text-dars-ink-soft flex items-baseline gap-2">
            <span className="text-dars-muted font-mono text-xs">
              Ch {group.chapter_position}
            </span>
            <span>{group.chapter_title}</span>
            <span className="ml-auto text-xs text-dars-muted font-normal">
              {group.slots.length} slot{group.slots.length === 1 ? "" : "s"}
            </span>
          </h2>

          <ul className="mt-2 space-y-2">
            {group.slots.map((slot) => (
              <li key={slot.id}>
                <LessonRow
                  slot={slot}
                  onViewLP={onViewLP}
                  onMarkTaught={onMarkTaught}
                  onSkip={onSkip}
                  busy={busySlotId === slot.id}
                />
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function LessonRow({
  slot,
  onViewLP,
  onMarkTaught,
  onSkip,
  busy,
}: {
  slot: ClassLessonSlotListItem;
  onViewLP: LessonsTabProps["onViewLP"];
  onMarkTaught: LessonsTabProps["onMarkTaught"];
  onSkip: LessonsTabProps["onSkip"];
  busy: boolean;
}) {
  const isRevision = slot.slot_type === "revision";
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex flex-col sm:flex-row sm:items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-xs font-mono text-dars-muted">
            #{slot.position}
          </span>
          {isRevision ? (
            <span className="text-[10px] font-semibold text-dars-terra uppercase tracking-wide">
              Revision
            </span>
          ) : null}
          {slot.lp_type ? (
            <span className="text-[10px] text-dars-muted-light font-mono">
              {slot.lp_type}
            </span>
          ) : null}
          <SlotStatusBadge status={slot.status} />
        </div>
        <p className="text-sm text-dars-ink truncate">
          {slot.topic_title ?? <em className="text-dars-muted">No topic</em>}
        </p>
        {slot.anchor_date ? (
          <p className="text-[10px] text-dars-muted-light mt-0.5">
            Anchored {slot.anchor_date}
          </p>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-2 shrink-0">
        <LPStatusPill lp_status={slot.lp_status} />
        <button
          type="button"
          onClick={() => onViewLP(slot)}
          className="px-2.5 py-1 rounded border border-dars-rule-dark text-xs text-dars-ink hover:bg-dars-parchment-deep"
        >
          View LP
        </button>
        {slot.status === "planned" ? (
          <>
            <button
              type="button"
              onClick={() => onMarkTaught(slot)}
              disabled={busy}
              className="px-2.5 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "…" : "Mark Taught"}
            </button>
            <button
              type="button"
              onClick={() => onSkip(slot)}
              disabled={busy}
              className="px-2.5 py-1 rounded border border-dars-rule-light text-xs text-dars-muted hover:bg-dars-parchment-deep disabled:opacity-50"
            >
              Skip
            </button>
          </>
        ) : null}
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
    <span className={"text-[10px] font-medium " + entry.cls}>● {entry.label}</span>
  );
}
