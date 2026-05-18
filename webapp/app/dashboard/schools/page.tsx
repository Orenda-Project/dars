/**
 * F5.5 — Schools list + create.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  admin,
  DarsApiError,
  tenancy as tenancyApi,
  type School,
} from "@/lib/dars-api";

export default function SchoolsPage() {
  const [schools, setSchools] = useState<School[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const { items } = await tenancyApi.getSchools();
      setSchools(items);
    } catch (err) {
      setError(formatErr(err));
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await admin.createSchool({ name: newName });
      setNewName("");
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
      <div className="flex items-center justify-between mb-4">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">Schools</h1>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold"
        >
          {showForm ? "Cancel" : "Add school"}
        </button>
      </div>

      {showForm ? (
        <form onSubmit={handleAdd} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 flex items-end gap-2">
          <label className="flex-1">
            <span className="text-xs text-dars-ink-soft">Name</span>
            <input
              required
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded border border-dars-rule-light bg-white text-sm"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="px-3 py-1.5 rounded bg-dars-ink text-dars-parchment text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Saving…" : "Create"}
          </button>
        </form>
      ) : null}

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-2">
        {schools.length === 0 ? (
          <li className="text-sm text-dars-muted">No schools yet.</li>
        ) : (
          schools.map((s) => (
            <li
              key={s.id}
              className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 flex items-center justify-between"
            >
              <div>
                <p className="font-medium text-dars-ink">{s.name}</p>
                <p className="text-[10px] font-mono text-dars-muted-light">{s.id.slice(0, 8)}…</p>
              </div>
              <Link
                href={`/dashboard/schools/${s.id}`}
                className="text-xs text-dars-terra hover:underline"
              >
                Manage →
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
