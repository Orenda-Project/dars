/**
 * F4.10 — SLO Progress tab template.
 *
 * "Have I taught these SLOs?" — per-SLO progress bar; expandable list
 * of sub-SLOs with their coverage status.
 */
"use client";

import { useState } from "react";

import type { SubSLOCoverageEntry } from "@/lib/dars-api";

export interface SLOProgressGroup {
  slo_id: string;
  slo_code: string;
  slo_statement: string;
  sub_slos: SubSLOCoverageEntry[];
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

  return (
    <div className="space-y-3">
      {joinedAtPosition > 1 ? (
        <p className="text-[11px] text-dars-muted-light mb-2">
          Joined this class mid-year (position {joinedAtPosition}). Sub-SLOs
          covered by earlier slots show as <em>unknown</em>.
        </p>
      ) : null}
      {groups.map((g) => (
        <SLOCard key={g.slo_id} group={g} />
      ))}
    </div>
  );
}

function SLOCard({ group }: { group: SLOProgressGroup }) {
  const [open, setOpen] = useState(false);

  const counts = group.sub_slos.reduce(
    (acc, x) => {
      acc.total += 1;
      acc[x.status] = (acc[x.status] ?? 0) + 1;
      return acc;
    },
    { total: 0, taught: 0, not_taught: 0, unknown: 0 } as Record<string, number>,
  );

  const taughtPct = counts.total === 0 ? 0 : Math.round((counts.taught / counts.total) * 100);

  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid">
      <button
        type="button"
        onClick={() => setOpen((x) => !x)}
        className="w-full text-left p-3 flex items-start gap-3"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-dars-muted">{group.slo_code}</span>
            <span className="text-[10px] text-dars-muted-light ml-auto">
              {counts.taught}/{counts.total} taught
            </span>
          </div>
          <p className="text-sm text-dars-ink line-clamp-2">{group.slo_statement}</p>
          <div className="mt-2 h-1.5 bg-dars-parchment-deep rounded overflow-hidden">
            <div
              className="h-full bg-dars-terra transition-all"
              style={{ width: `${taughtPct}%` }}
            />
          </div>
        </div>
        <span className="text-dars-muted text-xs">{open ? "▼" : "▶"}</span>
      </button>

      {open ? (
        <ul className="border-t border-dars-rule-light divide-y divide-dars-rule-light text-xs">
          {group.sub_slos.map((s) => (
            <li key={s.sub_slo_id} className="px-3 py-2 flex items-center gap-2">
              <span className="font-mono text-dars-muted">{s.sub_slo_code}</span>
              <StatusPill status={s.status} />
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    taught: "bg-emerald-100 text-emerald-800",
    not_taught: "bg-dars-parchment-deep text-dars-ink-soft",
    unknown: "bg-amber-100 text-amber-800",
  };
  return (
    <span
      className={
        "px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide " +
        (map[status] ?? "bg-dars-parchment-deep text-dars-muted")
      }
    >
      {status.replace("_", " ")}
    </span>
  );
}
