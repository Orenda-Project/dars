/**
 * F5.15 — SLO coverage (org-wide).
 *
 * v1 ships the org-wide view here (read-only). The per-class view
 * already exists in the teacher app's SLO Progress tab; the dashboard
 * surfaces the aggregate.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  adminGenerations,
  curriculum as curriculumApi,
  DarsApiError,
  type Grade,
  type SLOCoverageBucket,
  type Subject,
} from "@/lib/dars-api";

export default function CoveragePage() {
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [gradeId, setGradeId] = useState<string>("");
  const [subjectId, setSubjectId] = useState<string>("");
  const [items, setItems] = useState<SLOCoverageBucket[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const loadFilters = useCallback(async () => {
    try {
      const [{ items: gs }, { items: ss }] = await Promise.all([
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setGrades(gs);
      setSubjects(ss);
      if (!gradeId && gs[0]) setGradeId(gs[0].id);
      if (!subjectId && ss[0]) setSubjectId(ss[0].id);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [gradeId, subjectId]);

  useEffect(() => {
    loadFilters();
  }, [loadFilters]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminGenerations.getCoverageSummary({
        grade_id: gradeId || undefined,
        subject_id: subjectId || undefined,
      });
      setItems(res.items);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setLoading(false);
    }
  }, [gradeId, subjectId]);

  useEffect(() => {
    if (gradeId && subjectId) load();
  }, [load, gradeId, subjectId]);

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        SLO coverage (org-wide)
      </h1>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select
          value={gradeId}
          onChange={(e) => setGradeId(e.target.value)}
          className="px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm"
        >
          {grades.map((g) => (
            <option key={g.id} value={g.id}>{g.label}</option>
          ))}
        </select>
        <select
          value={subjectId}
          onChange={(e) => setSubjectId(e.target.value)}
          className="px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm"
        >
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>{s.code}</option>
          ))}
        </select>
        {loading ? <span className="text-xs text-dars-muted">Loading…</span> : null}
      </div>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-2">
        {items.length === 0 ? (
          <li className="text-sm text-dars-muted">No SLOs for this combination.</li>
        ) : (
          items.map((b) => {
            const pct = b.sub_slo_count === 0 ? 0 : Math.round((b.taught_count / b.sub_slo_count) * 100);
            return (
              <li
                key={b.slo_id}
                className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3"
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="font-mono text-xs text-dars-muted">{b.slo_code}</span>
                  <span className="text-[10px] text-dars-muted">
                    {b.taught_count}/{b.sub_slo_count} taught{" "}
                    {b.avg_mastery_percent !== null ? (
                      <>
                        · mastery {Math.round(b.avg_mastery_percent)}%
                      </>
                    ) : null}
                  </span>
                </div>
                <p className="text-sm text-dars-ink-soft line-clamp-2">{b.slo_statement}</p>
                <div className="mt-2 h-1.5 bg-dars-parchment-deep rounded overflow-hidden">
                  <div className="h-full bg-dars-terra" style={{ width: `${pct}%` }} />
                </div>
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
