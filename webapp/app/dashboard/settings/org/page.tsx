/**
 * F5.4 — Org settings + API key rotate.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  admin,
  curriculum as curriculumApi,
  DarsApiError,
  tenancy as tenancyApi,
  type AdminMeResponse,
  type Teacher,
} from "@/lib/dars-api";

export default function OrgSettingsPage() {
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [orgName, setOrgName] = useState("");
  const [defaultTeacherId, setDefaultTeacherId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [rotated, setRotated] = useState<string | null>(null);
  const [rotating, setRotating] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const m = await admin.me();
      setMe(m);
      setOrgName(m.org_name);
      setDefaultTeacherId(m.default_teacher_id ?? "");
      const { items } = await tenancyApi.getTeachers();
      setTeachers(items);
    } catch (err) {
      setError(formatErr(err));
    }
    void curriculumApi;
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setBusy(true);
    try {
      const next = await admin.patchOrg({
        name: orgName,
        default_teacher_id: defaultTeacherId || undefined,
      });
      setMe(next);
      setSuccess("Saved.");
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleRotate() {
    if (!confirm("Rotate the org API key? The old key will stop working immediately.")) return;
    setRotating(true);
    setRotated(null);
    setError(null);
    try {
      const res = await admin.rotateApiKey();
      setRotated(res.api_key);
      // Refresh me to pick up new prefix
      const m = await admin.me();
      setMe(m);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setRotating(false);
    }
  }

  if (!me) {
    return <p className="text-sm text-dars-muted">Loading…</p>;
  }

  return (
    <div className="max-w-xl space-y-8">
      <header>
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">Org settings</h1>
      </header>

      <form onSubmit={handleSave} className="space-y-4 rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
        <label className="block">
          <span className="text-xs text-dars-ink-soft">Org name</span>
          <input
            value={orgName}
            onChange={(e) => setOrgName(e.target.value)}
            className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-sm"
          />
        </label>
        <div className="text-xs text-dars-muted">
          <span className="text-dars-ink-soft font-medium">Curriculum:</span>{" "}
          <code className="font-mono">{me.curriculum_code}</code> (immutable — D-25)
        </div>
        <label className="block">
          <span className="text-xs text-dars-ink-soft">Default teacher (for teacher app)</span>
          <select
            value={defaultTeacherId}
            onChange={(e) => setDefaultTeacherId(e.target.value)}
            className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-sm"
          >
            <option value="">— none —</option>
            {teachers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name}
              </option>
            ))}
          </select>
        </label>
        {error ? <p className="text-sm text-dars-terra">{error}</p> : null}
        {success ? <p className="text-sm text-emerald-700">{success}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save"}
        </button>
      </form>

      <section className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
        <h2 className="text-sm font-semibold text-dars-ink mb-2">API key</h2>
        <p className="text-xs text-dars-muted mb-3">
          Current prefix: <code className="font-mono">{me.api_key_prefix}…</code>
        </p>
        {rotated ? (
          <div className="bg-emerald-50 border border-emerald-300 rounded p-3 mb-3 text-xs">
            <p className="font-semibold text-dars-ink mb-1">New API key — copy it now:</p>
            <code className="font-mono break-all">{rotated}</code>
          </div>
        ) : null}
        <button
          type="button"
          onClick={handleRotate}
          disabled={rotating}
          className="px-3 py-1.5 rounded border border-dars-terra/40 text-dars-terra text-xs font-semibold hover:bg-dars-terra/10 disabled:opacity-50"
        >
          {rotating ? "Rotating…" : "Rotate API key"}
        </button>
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
