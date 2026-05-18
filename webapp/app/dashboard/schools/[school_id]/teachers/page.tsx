/**
 * F5.6 — Teachers list per school + create/edit.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  admin,
  DarsApiError,
  tenancy as tenancyApi,
  type Teacher,
} from "@/lib/dars-api";

export default function TeachersPage() {
  const params = useParams<{ school_id: string }>();
  const schoolId = params.school_id;
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const { items } = await tenancyApi.getTeachers(schoolId);
      setTeachers(items);
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
      await admin.createTeacher({
        school_id: schoolId,
        name,
        email: email || undefined,
      });
      setName("");
      setEmail("");
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
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">Teachers</h1>
        <button
          type="button"
          onClick={() => setShowForm((s) => !s)}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold"
        >
          {showForm ? "Cancel" : "Add teacher"}
        </button>
      </div>

      {showForm ? (
        <form onSubmit={handleAdd} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 grid grid-cols-2 gap-2 items-end">
          <label>
            <span className="text-xs text-dars-ink-soft">Name</span>
            <input required value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full px-3 py-2 rounded border border-dars-rule-light bg-white text-sm" />
          </label>
          <label>
            <span className="text-xs text-dars-ink-soft">Email (optional)</span>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="mt-1 w-full px-3 py-2 rounded border border-dars-rule-light bg-white text-sm" />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="col-span-2 px-3 py-1.5 rounded bg-dars-ink text-dars-parchment text-xs font-semibold disabled:opacity-50"
          >
            {busy ? "Saving…" : "Create"}
          </button>
        </form>
      ) : null}

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <ul className="space-y-2">
        {teachers.length === 0 ? (
          <li className="text-sm text-dars-muted">No teachers yet.</li>
        ) : (
          teachers.map((t) => (
            <li
              key={t.id}
              className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3"
            >
              <p className="font-medium text-dars-ink">{t.name}</p>
              {t.email ? <p className="text-xs text-dars-muted">{t.email}</p> : null}
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
