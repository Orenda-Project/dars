/**
 * F5.13 — Generation status dashboard.
 *
 * Lists this org's most-recent published breakdowns and shows live
 * progress against each by polling /api/v1/breakdowns/{id}/generation-status
 * every 5 seconds while any bucket is non-terminal.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  admin,
  syllabusBreakdowns as syllabusBreakdownsApi,
  curriculum as curriculumApi,
  DarsApiError,
  type AdminMeResponse,
  type SyllabusBreakdown,
  type BreakdownGenerationStatus,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

const POLL_MS = 5000;
const MAX_POLLS = 80; // ~6.6 min ceiling per breakdown

interface Row {
  breakdown: SyllabusBreakdown;
  status: BreakdownGenerationStatus | null;
  loading: boolean;
}

export default function GenerationsPage() {
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const pollCounts = useRef<Record<string, number>>({});

  const load = useCallback(async () => {
    setError(null);
    try {
      const [m, all, { items: gs }, { items: ss }] = await Promise.all([
        admin.me(),
        syllabusBreakdownsApi.getBreakdowns(),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setMe(m);
      setGrades(gs);
      setSubjects(ss);
      const published = all.items
        .filter((b) => b.curriculum_id === m.curriculum_id && b.status === "published")
        .slice(0, 25);
      setRows(published.map((b) => ({ breakdown: b, status: null, loading: true })));
    } catch (err) {
      setError(formatErr(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // For each row, kick off a status poll.
  useEffect(() => {
    if (rows.length === 0) return;
    let cancelled = false;
    const timers: ReturnType<typeof setTimeout>[] = [];

    rows.forEach(async (row) => {
      const id = row.breakdown.id;
      pollCounts.current[id] = 0;
      const pump = async () => {
        if (cancelled) return;
        try {
          const next = await fetch(
            `${process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "")}/api/v1/breakdowns/${id}/generation-status`,
            {
              headers: {
                "X-Admin-Session": localStorage.getItem("dars_admin_session") ?? "",
              },
            },
          );
          if (cancelled) return;
          if (next.ok) {
            const data = (await next.json()) as BreakdownGenerationStatus;
            setRows((cur) =>
              cur.map((r) => (r.breakdown.id === id ? { ...r, status: data, loading: false } : r)),
            );
            const lpInFlight = data.lp.pending + data.lp.in_flight;
            const examInFlight = data.exam.pending + data.exam.in_flight;
            if (lpInFlight + examInFlight > 0 && pollCounts.current[id]! < MAX_POLLS) {
              pollCounts.current[id]! += 1;
              timers.push(setTimeout(pump, POLL_MS));
            }
          } else {
            setRows((cur) =>
              cur.map((r) => (r.breakdown.id === id ? { ...r, loading: false } : r)),
            );
          }
        } catch {
          if (!cancelled) {
            setRows((cur) =>
              cur.map((r) => (r.breakdown.id === id ? { ...r, loading: false } : r)),
            );
          }
        }
      };
      void pump();
    });

    return () => {
      cancelled = true;
      timers.forEach((t) => clearTimeout(t));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows.length]);

  const gradeLabel = (id: string) => grades.find((g) => g.id === id)?.code ?? "—";
  const subjectLabel = (id: string) => subjects.find((s) => s.id === id)?.code ?? "—";

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-2">
        Generation status
      </h1>
      <p className="text-xs text-dars-muted mb-4">
        Recent published syllabus breakdowns. Live-polls while there's anything in flight.
      </p>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      {rows.length === 0 ? (
        <p className="text-sm text-dars-muted">No published syllabus breakdowns yet.</p>
      ) : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li
              key={r.breakdown.id}
              className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3"
            >
              <div className="flex items-center justify-between gap-3 mb-2">
                <div>
                  <p className="font-medium text-dars-ink">
                    {gradeLabel(r.breakdown.grade_id)} ·{" "}
                    {subjectLabel(r.breakdown.subject_id)}
                  </p>
                  <p className="text-[10px] font-mono text-dars-muted-light">
                    {r.breakdown.id.slice(0, 8)}…
                  </p>
                </div>
                <Link
                  href={`/dashboard/syllabus-breakdowns/${r.breakdown.id}`}
                  className="text-xs text-dars-terra hover:underline"
                >
                  View →
                </Link>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <ProgressBucket label="LP" bucket={r.status?.lp} loading={r.loading} />
                <ProgressBucket label="Exam" bucket={r.status?.exam} loading={r.loading} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ProgressBucket({
  label,
  bucket,
  loading,
}: {
  label: string;
  bucket: BreakdownGenerationStatus["lp"] | undefined | null;
  loading: boolean;
}) {
  if (loading || !bucket) {
    return (
      <div className="rounded bg-dars-parchment border border-dars-rule-light p-2">
        <p className="text-xs font-semibold text-dars-ink-soft">{label}</p>
        <p className="text-xs text-dars-muted">Loading…</p>
      </div>
    );
  }
  const total = bucket.total || 1;
  const readyPct = Math.round((bucket.ready / total) * 100);
  const errPct = Math.round((bucket.error / total) * 100);
  const pendingPct = Math.round(((bucket.pending + bucket.in_flight) / total) * 100);
  return (
    <div className="rounded bg-dars-parchment border border-dars-rule-light p-2">
      <p className="text-xs font-semibold text-dars-ink-soft mb-1">{label}</p>
      <div className="flex h-1.5 rounded overflow-hidden bg-dars-parchment-deep">
        <div className="bg-emerald-500" style={{ width: `${readyPct}%` }} />
        <div className="bg-amber-500" style={{ width: `${pendingPct}%` }} />
        <div className="bg-dars-terra" style={{ width: `${errPct}%` }} />
      </div>
      <p className="text-[10px] text-dars-muted-light mt-1">
        {bucket.ready}/{bucket.total} ready · {bucket.in_flight} in flight ·{" "}
        {bucket.pending} pending · {bucket.error} error
      </p>
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
