/**
 * F5.14 — Failed LP / Exam list with one-click retry.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  adminGenerations,
  DarsApiError,
  type FailureExamListItem,
  type FailureLPListItem,
} from "@/lib/dars-api";

export default function FailuresPage() {
  const [lps, setLps] = useState<FailureLPListItem[]>([]);
  const [exams, setExams] = useState<FailureExamListItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await adminGenerations.listFailures();
      setLps(res.lps);
      setExams(res.exams);
    } catch (err) {
      setError(formatErr(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function retryLP(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await adminGenerations.retryLP(id);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusyId(null);
    }
  }

  async function retryExam(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await adminGenerations.retryExam(id);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        Generation failures
      </h1>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <section className="mb-6">
        <h2 className="text-sm font-semibold text-dars-ink mb-2">
          LPs ({lps.length})
        </h2>
        {lps.length === 0 ? (
          <p className="text-xs text-dars-muted">No failed LPs.</p>
        ) : (
          <ul className="space-y-2">
            {lps.map((r) => (
              <li
                key={r.id}
                className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex items-start gap-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono text-dars-muted-light truncate">
                    {r.cache_key ?? r.id}
                  </p>
                  <p className="text-sm text-dars-ink mt-1">
                    <span className="font-mono text-xs">{r.scope}</span>
                    {r.lp_type ? <span className="text-dars-muted ml-2">{r.lp_type}</span> : null}
                  </p>
                  <p className="text-xs text-dars-terra mt-1 line-clamp-2">
                    {r.error_message ?? "Unknown error"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => retryLP(r.id)}
                  disabled={busyId === r.id}
                  className="px-2.5 py-1 rounded border border-dars-terra/40 text-xs text-dars-terra hover:bg-dars-terra/10 disabled:opacity-50"
                >
                  {busyId === r.id ? "…" : "Retry"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold text-dars-ink mb-2">
          Exams ({exams.length})
        </h2>
        {exams.length === 0 ? (
          <p className="text-xs text-dars-muted">No failed exams.</p>
        ) : (
          <ul className="space-y-2">
            {exams.map((r) => (
              <li
                key={r.id}
                className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex items-start gap-3"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-mono text-dars-muted-light truncate">
                    {r.cache_key ?? r.id}
                  </p>
                  <p className="text-sm text-dars-ink mt-1">
                    <span className="font-mono text-xs">{r.scope}</span>
                    {r.generation_type ? (
                      <span className="text-dars-muted ml-2">{r.generation_type}</span>
                    ) : null}
                  </p>
                  <p className="text-xs text-dars-terra mt-1 line-clamp-2">
                    {r.error_message ?? "Unknown error"}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => retryExam(r.id)}
                  disabled={busyId === r.id}
                  className="px-2.5 py-1 rounded border border-dars-terra/40 text-xs text-dars-terra hover:bg-dars-terra/10 disabled:opacity-50"
                >
                  {busyId === r.id ? "…" : "Retry"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
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
