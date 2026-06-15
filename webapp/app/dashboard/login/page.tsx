/**
 * F5.3 — Login.
 */
"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { admin, DarsApiError, setApiKey, setAdminSession } from "@/lib/dars-api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await admin.login({ email, password });
      setAdminSession(res.session_token);
      // Login can't return the org API key (keys are hashed + shown-once), so
      // mint a fresh one now and stash it under dars_org_api_key. This is what
      // lets the teacher app run on a real X-API-Key without a separate setup
      // step. NOTE: rotation invalidates the org's previous key — any other
      // client using it must re-key. Non-fatal: if rotate fails, the admin
      // session still drives the teacher app via the X-Admin-Session fallback.
      try {
        const rotated = await admin.rotateApiKey();
        setApiKey(rotated.api_key);
      } catch {
        /* keep going — session fallback covers the teacher app */
      }
      router.replace("/dashboard/overview");
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? err.status === 401
            ? "Invalid email or password."
            : `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Login failed",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-dars-parchment flex items-center justify-center p-4">
      <div className="max-w-sm w-full">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-1">
          Dars dashboard
        </h1>
        <p className="text-sm text-dars-muted mb-6">Org admin login.</p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <label className="block">
            <span className="text-xs text-dars-ink-soft">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-sm"
            />
          </label>
          <label className="block">
            <span className="text-xs text-dars-ink-soft">Password</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-sm"
            />
          </label>
          {error ? <p className="text-sm text-dars-terra" role="alert">{error}</p> : null}
          <button
            type="submit"
            disabled={busy}
            className="w-full px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Logging in…" : "Log in"}
          </button>
        </form>

        <p className="text-xs text-dars-muted mt-6">
          New here?{" "}
          <Link href="/dashboard/signup" className="underline text-dars-terra">
            Create an org →
          </Link>
        </p>
      </div>
    </div>
  );
}
