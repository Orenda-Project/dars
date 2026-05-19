/**
 * F4.10 — SLO Progress tab template.
 *
 * "Have I taught these SLOs?" — SLO tree. Each SLO row shows a circular
 * progress ring (taught / total of its sub-SLOs); click to expand the
 * branch and reveal sub-SLO children with their individual coverage
 * status. The ring is the visual centrepiece — see atoms/progress-ring.
 */
"use client";

import { useState } from "react";

import { ProgressRing } from "@/components/atoms";
import type { SubSLOCoverageStatus } from "@/lib/dars-api";

// A sub-SLO row carries its coverage status plus the statement so the
// expanded view can show the human-readable text (not just the code).
export interface SLOTreeSubSLO {
  sub_slo_id: string;
  sub_slo_code: string;
  sub_slo_statement: string;
  status: SubSLOCoverageStatus;
}

export interface SLOProgressGroup {
  slo_id: string;
  slo_code: string;
  slo_statement: string;
  sub_slos: SLOTreeSubSLO[];
}

interface SLOProgressTabProps {
  groups: SLOProgressGroup[];
  joinedAtPosition: number;
}

export function ClassSLOProgressTab({ groups, joinedAtPosition }: SLOProgressTabProps) {
  if (groups.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No SLOs to display</p>
        <p className="text-xs text-dars-muted mt-1">
          Sub-SLO coverage shows up once the breakdown is published and slots have topics.
        </p>
      </div>
    );
  }

  // Roll-up across all SLOs for the page-level overview banner. We count
  // sub-SLOs because that's where status actually lives; an SLO is fully
  // taught only when every one of its sub-SLOs is taught.
  const overall = groups.reduce(
    (acc, g) => {
      for (const s of g.sub_slos) {
        acc.total += 1;
        if (s.status === "taught") acc.taught += 1;
      }
      return acc;
    },
    { taught: 0, total: 0 },
  );
  const overallPct =
    overall.total === 0 ? 0 : Math.round((overall.taught / overall.total) * 100);

  return (
    <div className="space-y-4">
      <OverviewBanner
        pct={overallPct}
        taught={overall.taught}
        total={overall.total}
        sloCount={groups.length}
        joinedAtPosition={joinedAtPosition}
      />

      <ol className="space-y-3">
        {groups.map((g) => (
          <li key={g.slo_id}>
            <SLOTreeNode group={g} />
          </li>
        ))}
      </ol>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview banner
// ---------------------------------------------------------------------------

function OverviewBanner({
  pct,
  taught,
  total,
  sloCount,
  joinedAtPosition,
}: {
  pct: number;
  taught: number;
  total: number;
  sloCount: number;
  joinedAtPosition: number;
}) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 flex items-center gap-4">
      <ProgressRing
        value={pct}
        size={88}
        strokeWidth={8}
        caption={`${taught}/${total}`}
        label={`Overall coverage ${pct}%`}
      />
      <div className="flex-1 min-w-0">
        <p className="text-[11px] uppercase tracking-[1.5px] text-dars-terra font-bold">
          SLO Coverage
        </p>
        <h2 className="font-serif text-lg font-bold text-dars-ink mt-0.5">
          {pct === 100
            ? "All sub-SLOs taught — well done."
            : pct === 0
              ? "Nothing taught yet for this year"
              : `${taught} of ${total} sub-SLOs taught`}
        </h2>
        <p className="text-xs text-dars-muted mt-1">
          {sloCount} SLO{sloCount === 1 ? "" : "s"} in this scheme · expand a
          row to see the breakdown.
        </p>
        {joinedAtPosition > 1 ? (
          <p className="text-[11px] text-dars-muted-light italic mt-1.5">
            Joined this class mid-year at position {joinedAtPosition}. Sub-SLOs
            covered by earlier slots show as <em>unknown</em>.
          </p>
        ) : null}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tree node — one SLO with ring + collapsible sub-SLO list
// ---------------------------------------------------------------------------

function SLOTreeNode({ group }: { group: SLOProgressGroup }) {
  const [open, setOpen] = useState(false);

  const counts = group.sub_slos.reduce(
    (acc, x) => {
      acc.total += 1;
      acc[x.status] += 1;
      return acc;
    },
    { total: 0, taught: 0, not_taught: 0, unknown: 0 } as Record<string, number>,
  );

  // Denominator excludes "unknown" so a teacher who joined late isn't
  // perpetually under 100%. If everything we can score is taught, the
  // ring fills — the unknown bucket is surfaced in the badge strip.
  const scoreable = counts.total - counts.unknown;
  const taughtPct =
    scoreable <= 0 ? 0 : Math.round((counts.taught / scoreable) * 100);

  const isEmpty = group.sub_slos.length === 0;

  return (
    <div
      className={
        "rounded-md border bg-dars-parchment-mid transition-colors " +
        (open
          ? "border-dars-terra/40 shadow-sm"
          : "border-dars-rule-light hover:border-dars-rule-dark/30")
      }
    >
      <button
        type="button"
        onClick={() => setOpen((x) => !x)}
        disabled={isEmpty}
        aria-expanded={open}
        aria-controls={`slo-${group.slo_id}-children`}
        className="w-full text-left p-4 flex items-center gap-4 disabled:cursor-not-allowed disabled:opacity-70"
      >
        <ProgressRing
          value={taughtPct}
          size={64}
          strokeWidth={6}
          caption={
            counts.total === 0 ? "—" : `${counts.taught}/${counts.total}`
          }
          label={`${group.slo_code} ${taughtPct}% taught`}
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center flex-wrap gap-x-2 gap-y-1 mb-1">
            <span className="font-mono text-xs text-dars-terra font-semibold">
              {group.slo_code}
            </span>
            {counts.unknown > 0 ? (
              <span className="text-[10px] font-semibold uppercase tracking-wide bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">
                {counts.unknown} unknown
              </span>
            ) : null}
            {counts.total > 0 && counts.taught === counts.total ? (
              <span className="text-[10px] font-semibold uppercase tracking-wide bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded">
                Complete
              </span>
            ) : null}
          </div>
          <p className="font-serif text-sm text-dars-ink leading-snug">
            {group.slo_statement}
          </p>
          {isEmpty ? (
            <p className="text-[11px] text-dars-muted-light italic mt-1.5">
              No sub-SLOs registered for this outcome.
            </p>
          ) : null}
        </div>

        {!isEmpty ? (
          <Chevron open={open} />
        ) : null}
      </button>

      {open && !isEmpty ? (
        <div
          id={`slo-${group.slo_id}-children`}
          className="border-t border-dars-rule-light bg-dars-parchment/60"
        >
          <ol className="px-4 py-2">
            {group.sub_slos.map((s, idx) => (
              <li key={s.sub_slo_id}>
                <SubSLORow
                  subSlo={s}
                  isLast={idx === group.sub_slos.length - 1}
                />
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-SLO leaf — branch glyph + status dot + statement
// ---------------------------------------------------------------------------

function SubSLORow({
  subSlo,
  isLast,
}: {
  subSlo: SLOTreeSubSLO;
  isLast: boolean;
}) {
  return (
    <div className="grid grid-cols-[20px_1fr] items-stretch">
      {/* Tree branch glyph: a vertical guideline + an elbow into the row.
          We draw it with absolute-positioned divs so the line can extend
          through the row's full height without affecting layout. */}
      <div className="relative">
        <span
          className={
            "absolute left-1/2 top-0 w-px bg-dars-rule-light " +
            (isLast ? "h-1/2" : "h-full")
          }
          aria-hidden="true"
        />
        <span
          className="absolute left-1/2 top-1/2 h-px w-2 bg-dars-rule-light"
          aria-hidden="true"
        />
      </div>

      <div className="py-2 pl-3 flex items-start gap-3 min-w-0">
        <StatusDot status={subSlo.status} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="font-mono text-[11px] text-dars-muted">
              {subSlo.sub_slo_code}
            </span>
            <StatusLabel status={subSlo.status} />
          </div>
          {subSlo.sub_slo_statement ? (
            <p className="text-xs text-dars-ink-soft leading-snug">
              {subSlo.sub_slo_statement}
            </p>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function StatusDot({ status }: { status: SubSLOCoverageStatus }) {
  const cls =
    status === "taught"
      ? "bg-emerald-500 ring-emerald-200"
      : status === "unknown"
        ? "bg-amber-400 ring-amber-100"
        : "bg-dars-rule-light ring-dars-parchment-deep";
  return (
    <span
      className={"mt-1 h-2.5 w-2.5 rounded-full ring-4 shrink-0 " + cls}
      aria-hidden="true"
    />
  );
}

function StatusLabel({ status }: { status: SubSLOCoverageStatus }) {
  const map: Record<SubSLOCoverageStatus, { text: string; cls: string }> = {
    taught: { text: "Taught", cls: "text-emerald-700" },
    not_taught: { text: "Not taught", cls: "text-dars-muted" },
    unknown: { text: "Unknown", cls: "text-amber-700" },
  };
  const entry = map[status];
  return (
    <span
      className={
        "text-[10px] font-semibold uppercase tracking-wide " + entry.cls
      }
    >
      {entry.text}
    </span>
  );
}

function Chevron({ open }: { open: boolean }) {
  return (
    <span
      className="shrink-0 text-dars-muted-light"
      aria-hidden="true"
      style={{
        display: "inline-block",
        transition: "transform 200ms ease-out",
        transform: open ? "rotate(90deg)" : "rotate(0deg)",
      }}
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path
          d="M6 4l4 4-4 4"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}
