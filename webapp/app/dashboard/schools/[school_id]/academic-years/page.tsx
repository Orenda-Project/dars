/**
 * F5.7 — Academic years per school.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  admin,
  DarsApiError,
  tenancy as tenancyApi,
  type AcademicYear,
} from "@/lib/dars-api";

export default function AcademicYearsPage() {
  const params = useParams<{ school_id: string }>();
  const schoolId = params.school_id;
  const [ays, setAys] = useState<AcademicYear[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const { items } = await tenancyApi.getAcademicYears(schoolId);
      setAys(items);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [schoolId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await admin.createAcademicYear({
        school_id: schoolId,
        name,
        start_date: start,
        end_date: end,
      });
      setName("");
      setStart("");
      setEnd("");
      setShowForm(false);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="text-xs text-dars-muted mb-2">
        <Link href={`/dashboard/schools/${schoolId}`} className="hover:text-dars-terra">
          ← Back to school
        </Link>
      </div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">Academic years</h1>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold"
        >
          {showForm ? "Cancel" : "Add AY"}
        </button>
      </div>

      {showForm ? (
        <form onSubmit={handleAdd} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 grid grid-cols-3 gap-2 items-end">
          <label>
            <span className="text-xs text-dars-ink-soft">Name</span>
            <input required value={name} onChange={(e) => setName(e.target.value)} className="input" placeholder="2026–2027" />
          </label>
          <label>
            <span className="text-xs text-dars-ink-soft">Start date</span>
            <input required type="date" value={start} onChange={(e) => setStart(e.target.value)} className="input" />
          </label>
          <label>
            <span className="text-xs text-dars-ink-soft">End date</span>
            <input required type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="input" />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="col-span-3 px-3 py-1.5 rounded bg-dars-ink text-dars-parchment text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Saving…" : "Create"}
          </button>
          <style jsx>{`
            .input {
              margin-top: 0.25rem;
              width: 100%;
              padding: 0.5rem 0.75rem;
              border-radius: 0.375rem;
              border: 1px solid var(--color-dars-rule-light);
              background: white;
              font-size: 0.875rem;
            }
          `}</style>
        </form>
      ) : null}

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-2">
        {ays.length === 0 ? (
          <li className="text-sm text-dars-muted">No academic years yet.</li>
        ) : (
          ays.map((a) => (
            <li
              key={a.id}
              className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex items-center justify-between"
            >
              <div>
                <p className="font-medium text-dars-ink">{a.name}</p>
                <p className="text-xs text-dars-muted font-mono">
                  {a.start_date} → {a.end_date}
                </p>
              </div>
              <Link
                href={`/dashboard/schools/${schoolId}/academic-years/${a.id}/classes`}
                className="text-xs text-dars-terra hover:underline"
              >
                Manage classes →
              </Link>
            </li>
          ))
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
