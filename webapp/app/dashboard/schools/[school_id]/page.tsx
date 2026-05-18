/**
 * F5.5/F5.6 — School detail: edit name + nav to teachers + nav to AYs.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  admin,
  DarsApiError,
  tenancy as tenancyApi,
  type School,
} from "@/lib/dars-api";

export default function SchoolDetailPage() {
  const params = useParams<{ school_id: string }>();
  const schoolId = params.school_id;
  const [school, setSchool] = useState<School | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const s = await tenancyApi.getSchool(schoolId);
      setSchool(s);
      setName(s.name);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [schoolId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await admin.updateSchool(schoolId, { name });
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  if (!school) return <p className="text-sm text-dars-muted">Loading…</p>;

  return (
    <div className="max-w-xl space-y-5">
      <div className="text-xs text-dars-muted">
        <Link href="/dashboard/schools" className="hover:text-dars-terra">← All schools</Link>
      </div>
      <header>
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">{school.name}</h1>
      </header>

      <form onSubmit={handleSave} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex items-end gap-2">
        <label className="flex-1">
          <span className="text-xs text-dars-ink-soft">Name</span>
          <input
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1 w-full px-3 py-2 rounded border border-dars-rule-light bg-white text-sm"
          />
        </label>
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </form>
      {error ? <p className="text-sm text-dars-terra">{error}</p> : null}

      <nav className="grid grid-cols-2 gap-2">
        <Link
          href={`/dashboard/schools/${schoolId}/teachers`}
          className="rounded border border-dars-rule-light bg-dars-parchment-mid p-3 text-sm hover:bg-dars-parchment-deep"
        >
          Teachers →
        </Link>
        <Link
          href={`/dashboard/schools/${schoolId}/academic-years`}
          className="rounded border border-dars-rule-light bg-dars-parchment-mid p-3 text-sm hover:bg-dars-parchment-deep"
        >
          Academic years →
        </Link>
      </nav>
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
