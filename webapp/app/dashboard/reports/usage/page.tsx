/**
 * F5.16 — Cost & usage report.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import { DarsApiError, usage as usageApi, type UsageReport } from "@/lib/dars-api";

export default function UsageReportPage() {
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [data, setData] = useState<UsageReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await usageApi.getOrgUsage({ start: start || undefined, end: end || undefined }));
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setLoading(false);
    }
  }, [start, end]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        Usage & cost
      </h1>

      <div className="flex items-end gap-2 mb-4">
        <label>
          <span className="text-xs text-dars-ink-soft">Start</span>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="block mt-1 px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm" />
        </label>
        <label>
          <span className="text-xs text-dars-ink-soft">End</span>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="block mt-1 px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm" />
        </label>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      {data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Stat label="LPs generated" value={data.lp_count} />
            <Stat label="Exams generated" value={data.exam_count} />
            <Stat label="Total cost" value={`$${data.total_cost_usd.toFixed(4)}`} />
          </div>

          <section>
            <h2 className="text-sm font-semibold text-dars-ink mb-2">By subject</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-dars-muted border-b border-dars-rule-light">
                  <th className="py-1">Subject</th>
                  <th className="py-1 text-right">LPs</th>
                  <th className="py-1 text-right">Exams</th>
                  <th className="py-1 text-right">Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {data.by_subject.length === 0 ? (
                  <tr><td colSpan={4} className="text-xs text-dars-muted py-2">No data</td></tr>
                ) : (
                  data.by_subject.map((r) => (
                    <tr key={r.subject_code} className="border-b border-dars-rule-light">
                      <td className="py-1.5 font-mono text-xs">{r.subject_code}</td>
                      <td className="py-1.5 text-right">{r.lp_count}</td>
                      <td className="py-1.5 text-right">{r.exam_count}</td>
                      <td className="py-1.5 text-right font-mono text-xs">${r.cost_usd.toFixed(4)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <section>
            <h2 className="text-sm font-semibold text-dars-ink mb-2">By curriculum</h2>
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-dars-muted border-b border-dars-rule-light">
                  <th className="py-1">Curriculum</th>
                  <th className="py-1 text-right">LPs</th>
                  <th className="py-1 text-right">Exams</th>
                  <th className="py-1 text-right">Cost (USD)</th>
                </tr>
              </thead>
              <tbody>
                {data.by_curriculum.length === 0 ? (
                  <tr><td colSpan={4} className="text-xs text-dars-muted py-2">No data</td></tr>
                ) : (
                  data.by_curriculum.map((r) => (
                    <tr key={r.curriculum_code} className="border-b border-dars-rule-light">
                      <td className="py-1.5 font-mono text-xs">{r.curriculum_code}</td>
                      <td className="py-1.5 text-right">{r.lp_count}</td>
                      <td className="py-1.5 text-right">{r.exam_count}</td>
                      <td className="py-1.5 text-right font-mono text-xs">${r.cost_usd.toFixed(4)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </section>

          <p className="text-[10px] text-dars-muted-light">
            v1 attribution: class-scope rows only. Global cache rows shared across orgs aren’t double-counted here.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
      <p className="text-xs text-dars-muted">{label}</p>
      <p className="text-xl font-bold text-dars-ink mt-1 font-[var(--font-cormorant)]">{value}</p>
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
