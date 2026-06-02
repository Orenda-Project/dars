/**
 * Syllabus breakdowns list (global, read-mostly).
 *
 * Lists the global syllabus breakdowns for the org's curriculum — one per
 * grade × subject. Each is a chapter→date-range plan. Open one to edit its
 * chapter date ranges and publish.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  admin,
  syllabusBreakdowns as syllabusBreakdownsApi,
  curriculum as curriculumApi,
  DarsApiError,
  type AdminMeResponse,
  type SyllabusBreakdown,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

export default function SyllabusBreakdownsPage() {
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [items, setItems] = useState<SyllabusBreakdown[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [m, list, { items: gs }, { items: ss }] = await Promise.all([
        admin.me(),
        syllabusBreakdownsApi.getBreakdowns(),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setMe(m);
      setItems(list.items.filter((b) => b.curriculum_id === m.curriculum_id));
      setGrades(gs);
      setSubjects(ss);
    } catch (err) {
      setError(formatErr(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handlePublish(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await syllabusBreakdownsApi.publish(id);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusyId(null);
    }
  }

  const gradeById = useMemo(
    () => new Map(grades.map((g) => [g.id, g])),
    [grades],
  );
  const subjectById = useMemo(
    () => new Map(subjects.map((s) => [s.id, s])),
    [subjects],
  );

  const breakdownLabel = (b: SyllabusBreakdown): string => {
    const curriculumCode = me?.curriculum_code ?? "—";
    const gradeLabel = gradeById.get(b.grade_id)?.display_name ?? "—";
    const subjectCode = subjectById.get(b.subject_id)?.code ?? "—";
    return `${curriculumCode} · ${gradeLabel} · ${subjectCode}`;
  };

  return (
    <div>
      <div className="flex items-end justify-between mb-4 gap-3">
        <div>
          <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
            Syllabus Breakdowns
          </h1>
          <p className="text-sm text-dars-muted mt-1 max-w-2xl">
            Global chapter→date-range plans, one per grade × subject. Open one
            to set each chapter's teaching dates and publish.
          </p>
        </div>
      </div>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      {items.length === 0 ? (
        <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
          <p className="text-sm font-medium text-dars-ink">
            No syllabus breakdowns yet.
          </p>
        </div>
      ) : (
        <ul className="space-y-2">
          {items.map((b) => (
            <li
              key={b.id}
              className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex items-center justify-between gap-3"
            >
              <div className="min-w-0">
                <p className="font-medium text-dars-ink truncate">
                  {breakdownLabel(b)}
                </p>
                <p className="text-[10px] font-mono text-dars-muted-light mt-0.5">
                  {b.id.slice(0, 8)}…
                </p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <StatusBadge status={b.status} />
                <Link
                  href={`/dashboard/syllabus-breakdowns/${b.id}`}
                  className="text-xs text-dars-terra hover:underline"
                >
                  View
                </Link>
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
              </div>
            </li>
          ))}
        </ul>
      )}
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
    <span
      className={
        "px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wide " +
        (map[status] ?? "bg-dars-parchment-deep text-dars-muted")
      }
    >
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
