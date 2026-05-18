/**
 * F5.10 — Breakdowns list with fork / publish / view.
 *
 * Shows breakdowns visible to this org's curriculum:
 *   - global-scope (forkable templates)
 *   - org-scope (this org's own)
 *   - class-scope (per-CST)
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  admin,
  breakdowns as breakdownsApi,
  curriculum as curriculumApi,
  DarsApiError,
  type AdminMeResponse,
  type Breakdown,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

type ScopeFilter = "all" | "global" | "org" | "class";

export default function BreakdownsPage() {
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [items, setItems] = useState<Breakdown[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [scopeFilter, setScopeFilter] = useState<ScopeFilter>("all");
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [m, all, { items: gs }, { items: ss }] = await Promise.all([
        admin.me(),
        breakdownsApi.getBreakdowns(),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setMe(m);
      setItems(all.items.filter((b) => b.curriculum_id === m.curriculum_id));
      setGrades(gs);
      setSubjects(ss);
    } catch (err) {
      setError(formatErr(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = useMemo(
    () => (scopeFilter === "all" ? items : items.filter((b) => b.scope === scopeFilter)),
    [items, scopeFilter],
  );

  async function handleForkOrg(global_id: string) {
    if (!me) return;
    setBusyId(global_id);
    setError(null);
    try {
      await breakdownsApi.forkOrg(global_id, { org_id: me.org_id });
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusyId(null);
    }
  }

  async function handlePublish(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await breakdownsApi.publish(id);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusyId(null);
    }
  }

  const gradeLabel = (id: string) => grades.find((g) => g.id === id)?.code ?? "—";
  const subjectLabel = (id: string) => subjects.find((s) => s.id === id)?.code ?? "—";

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        Breakdowns
      </h1>

      <div className="flex gap-1 mb-4 text-xs">
        {(["all", "global", "org", "class"] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setScopeFilter(s)}
            className={
              "px-2.5 py-1 rounded " +
              (scopeFilter === s
                ? "bg-dars-terra text-dars-parchment font-semibold"
                : "bg-dars-parchment-mid text-dars-ink-soft hover:bg-dars-parchment-deep")
            }
          >
            {s}
          </button>
        ))}
      </div>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs text-dars-muted border-b border-dars-rule-light">
            <th className="py-1">Scope</th>
            <th className="py-1">Grade</th>
            <th className="py-1">Subject</th>
            <th className="py-1">Status</th>
            <th className="py-1 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          {filtered.length === 0 ? (
            <tr><td colSpan={5} className="text-xs text-dars-muted py-2">No breakdowns.</td></tr>
          ) : (
            filtered.map((b) => (
              <tr key={b.id} className="border-b border-dars-rule-light">
                <td className="py-1.5">
                  <span className="font-mono text-xs">{b.scope}</span>
                </td>
                <td className="py-1.5 font-mono text-xs">{gradeLabel(b.grade_id)}</td>
                <td className="py-1.5 font-mono text-xs">{subjectLabel(b.subject_id)}</td>
                <td className="py-1.5">
                  <StatusBadge status={b.status} />
                </td>
                <td className="py-1.5 text-right space-x-2">
                  <Link
                    href={`/dashboard/breakdowns/${b.id}`}
                    className="text-xs text-dars-terra hover:underline"
                  >
                    View
                  </Link>
                  {b.scope === "global" && b.status === "published" ? (
                    <button
                      type="button"
                      onClick={() => handleForkOrg(b.id)}
                      disabled={busyId === b.id}
                      className="text-xs text-dars-ink hover:underline disabled:opacity-50"
                    >
                      Fork to org
                    </button>
                  ) : null}
                  {b.status === "draft" ? (
                    <button
                      type="button"
                      onClick={() => handlePublish(b.id)}
                      disabled={busyId === b.id}
                      className="text-xs text-dars-ink hover:underline disabled:opacity-50"
                    >
                      Publish
                    </button>
                  ) : null}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    draft: "bg-amber-100 text-amber-800",
    published: "bg-emerald-100 text-emerald-800",
    deleted: "bg-dars-parchment-deep text-dars-muted",
  };
  return (
    <span className={"px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide " + (map[status] ?? "bg-dars-parchment-deep text-dars-muted")}>
      {status}
    </span>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
