/**
 * F5.3 — Signup (create org + first admin).
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import {
  admin,
  clearApiKey,
  curriculum as curriculumApi,
  DarsApiError,
  setAdminSession,
  type Curriculum,
} from "@/lib/dars-api";

export default function SignupPage() {
  const router = useRouter();
  const [curriculums, setCurriculums] = useState<Curriculum[]>([]);
  const [orgName, setOrgName] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [curriculumCode, setCurriculumCode] = useState("DARS");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<{ apiKey: string } | null>(null);

  useEffect(() => {
    // Curriculums list is publicly readable (no auth-required endpoint
    // for it in dars-api, but the request always needs *some* auth
    // header). For signup we bypass: hit fetch directly.
    (async () => {
      try {
        const base = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "";
        const res = await fetch(`${base}/api/v2/curriculums`);
        if (!res.ok) return;
        const data = (await res.json()) as { items: Curriculum[] };
        setCurriculums(data.items);
      } catch {
        // ignore — admins can still type a code
      }
    })();
    void curriculumApi;
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await admin.signup({
        email,
        password,
        name,
        org_name: orgName,
        curriculum_code: curriculumCode,
      });
      // Drop any org API key left in this browser by a previous account.
      // request() prefers X-API-Key over X-Admin-Session, so a stale key
      // from another org would make the new dashboard authenticate as that
      // org and show its data — a cross-tenant leak. The new org's key is
      // shown once below and not stored; the dashboard runs on the admin
      // session fallback. (Logout clears both keys as a pair — signup must too.)
      clearApiKey();
      setAdminSession(res.session_token);
      setCreated({ apiKey: res.api_key });
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Signup failed",
      );
    } finally {
      setBusy(false);
    }
  }

  if (created) {
    return (
      <div className="min-h-screen bg-dars-parchment flex items-center justify-center p-4">
        <div className="max-w-md w-full">
          <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-2">
            Org created
          </h1>
          <p className="text-sm text-dars-muted mb-4">
            Your first API key is shown once. Copy it now — it isn’t recoverable.
          </p>
          <div className="bg-dars-parchment-mid border border-dars-rule-light rounded-md p-3 mb-4">
            <code className="text-xs font-mono text-dars-ink break-all">{created.apiKey}</code>
          </div>
          <button
            type="button"
            onClick={() => router.replace("/dashboard/overview")}
            className="w-full px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90"
          >
            Continue to dashboard →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-dars-parchment flex items-center justify-center p-4">
      <div className="max-w-sm w-full">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-1">
          Create your org
        </h1>
        <p className="text-sm text-dars-muted mb-6">
          One curriculum per org (D-25). Pick the one you’ll teach.
        </p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <Field label="Org name">
            <input
              type="text"
              required
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="input"
            />
          </Field>
          <Field label="Your name">
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="input"
            />
          </Field>
          <Field label="Email">
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="input"
            />
          </Field>
          <Field label="Password">
            <input
              type="password"
              required
              minLength={8}
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="input"
            />
          </Field>
          <Field label="Curriculum">
            <select
              value={curriculumCode}
              onChange={(e) => setCurriculumCode(e.target.value)}
              className="input"
            >
              {curriculums.length > 0
                ? curriculums.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.code} — {c.name}
                    </option>
                  ))
                : (
                  <>
                    <option value="DARS">DARS</option>
                    <option value="NCP">NCP</option>
                    <option value="SNC">SNC</option>
                  </>
                )}
            </select>
          </Field>

          {error ? <p className="text-sm text-dars-terra" role="alert">{error}</p> : null}

          <button
            type="submit"
            disabled={busy}
            className="w-full px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Creating…" : "Create org →"}
          </button>
        </form>

        <p className="text-xs text-dars-muted mt-6">
          Already have an account?{" "}
          <Link href="/dashboard/login" className="underline text-dars-terra">
            Log in
          </Link>
        </p>

        <style jsx>{`
          .input {
            width: 100%;
            margin-top: 0.25rem;
            padding: 0.5rem 0.75rem;
            border-radius: 0.375rem;
            border: 1px solid var(--color-dars-rule-light);
            background: white;
            font-size: 0.875rem;
          }
        `}</style>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-xs text-dars-ink-soft">{label}</span>
      {children}
    </label>
  );
}
