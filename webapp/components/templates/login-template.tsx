"use client";

import { useState } from "react";
import { Logo } from "@/components/atoms/logo";

type Tab = "signin" | "signup";

interface AuthResult {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
}

export function LoginTemplate() {
  const [tab, setTab] = useState<Tab>("signin");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AuthResult | null>(null);
  const [copied, setCopied] = useState(false);

  // Sign In state
  const [siEmail, setSiEmail] = useState("");
  const [siPassword, setSiPassword] = useState("");

  // Sign Up state
  const [suName, setSuName] = useState("");
  const [suEmail, setSuEmail] = useState("");
  const [suPassword, setSuPassword] = useState("");

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  function switchTab(next: Tab) {
    setTab(next);
    setError(null);
    setResult(null);
    setCopied(false);
  }

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: siEmail, password: siPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Sign in failed.");
      const authResult = data as AuthResult;
      localStorage.setItem("dars_session", JSON.stringify(authResult));
      window.location.href = "/dashboard";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${apiBase}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: suEmail, password: suPassword, name: suName }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail ?? "Sign up failed.");
      const authResult = data as AuthResult;
      localStorage.setItem("dars_session", JSON.stringify(authResult));
      setResult(authResult);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An unexpected error occurred.");
    } finally {
      setLoading(false);
    }
  }

  async function copyKey() {
    if (!result) return;
    await navigator.clipboard.writeText(result.api_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <main className="min-h-screen bg-dars-parchment flex flex-col items-center justify-center px-4 py-16">
      {/* Header */}
      <div className="mb-8 flex flex-col items-center gap-2">
        <a href="/" className="no-underline">
          <Logo size="md" />
        </a>
        <p className="text-sm text-dars-muted mt-1">
          {tab === "signin" ? "Sign in to your account" : "Create a new account"}
        </p>
      </div>

      {/* Card */}
      <div className="w-full max-w-md bg-white border border-dars-rule-light rounded-lg shadow-sm overflow-hidden">

        {/* Tab switcher */}
        <div className="flex border-b border-dars-rule-light">
          <button
            onClick={() => switchTab("signin")}
            className={`flex-1 py-3 text-sm font-semibold transition-colors cursor-pointer ${
              tab === "signin"
                ? "text-dars-ink border-b-2 border-dars-terra bg-dars-parchment"
                : "text-dars-muted bg-white hover:text-dars-ink"
            }`}
          >
            Sign In
          </button>
          <button
            onClick={() => switchTab("signup")}
            className={`flex-1 py-3 text-sm font-semibold transition-colors cursor-pointer ${
              tab === "signup"
                ? "text-dars-ink border-b-2 border-dars-terra bg-dars-parchment"
                : "text-dars-muted bg-white hover:text-dars-ink"
            }`}
          >
            Sign Up
          </button>
        </div>

        <div className="p-8">
          {/* Error */}
          {error && (
            <div className="mb-5 px-4 py-3 rounded-md bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          {/* Success — API key display */}
          {result ? (
            <div className="space-y-4">
              <p className="text-sm text-dars-ink">
                Welcome, <span className="font-semibold">{result.name}</span>. Your API key is ready.
              </p>

              <div className="rounded-md bg-dars-parchment border border-dars-rule-light p-4">
                <p className="text-xs text-dars-muted mb-2 font-mono tracking-wide uppercase">API Key</p>
                <div className="flex items-center gap-2">
                  <code className="font-mono text-xs text-dars-ink break-all flex-1 select-all">
                    {result.api_key}
                  </code>
                  <button
                    onClick={copyKey}
                    className="shrink-0 text-xs px-3 py-1.5 rounded bg-dars-terra text-white font-semibold hover:opacity-90 transition-opacity cursor-pointer"
                  >
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
              </div>

              <div className="rounded-md bg-amber-50 border border-amber-200 px-4 py-3 text-xs text-amber-800 leading-relaxed">
                <span className="font-bold">Save this key — it won&apos;t be shown again.</span> Store it in a secure place such as a secrets manager or environment variable.
              </div>

              <p className="text-xs text-dars-muted">
                Client ID: <span className="font-mono">{result.client_id}</span>
              </p>

              <button
                onClick={() => { window.location.href = "/dashboard"; }}
                className="w-full bg-dars-terra text-white py-2.5 rounded-md text-sm font-semibold hover:opacity-90 transition-opacity cursor-pointer"
              >
                Continue to Dashboard
              </button>
            </div>
          ) : tab === "signin" ? (
            /* Sign In form */
            <form onSubmit={handleSignIn} className="space-y-5">
              <p className="text-xs text-dars-muted leading-relaxed border-l-2 border-dars-terra pl-3">
                Note: Signing in rotates your API key. Store it safely.
              </p>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-dars-ink tracking-wide uppercase" htmlFor="si-email">
                  Email
                </label>
                <input
                  id="si-email"
                  type="email"
                  required
                  value={siEmail}
                  onChange={(e) => setSiEmail(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-dars-rule-light rounded-md bg-dars-parchment text-dars-ink placeholder:text-dars-muted-light focus:outline-none focus:border-dars-terra transition-colors"
                  placeholder="you@yourorg.com"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-dars-ink tracking-wide uppercase" htmlFor="si-password">
                  Password
                </label>
                <input
                  id="si-password"
                  type="password"
                  required
                  value={siPassword}
                  onChange={(e) => setSiPassword(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-dars-rule-light rounded-md bg-dars-parchment text-dars-ink placeholder:text-dars-muted-light focus:outline-none focus:border-dars-terra transition-colors"
                  placeholder="••••••••"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-dars-terra text-white py-2.5 rounded-md text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
              >
                {loading ? "Signing in…" : "Sign In"}
              </button>
            </form>
          ) : (
            /* Sign Up form */
            <form onSubmit={handleSignUp} className="space-y-5">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-dars-ink tracking-wide uppercase" htmlFor="su-name">
                  Organisation / Client Name
                </label>
                <input
                  id="su-name"
                  type="text"
                  required
                  value={suName}
                  onChange={(e) => setSuName(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-dars-rule-light rounded-md bg-dars-parchment text-dars-ink placeholder:text-dars-muted-light focus:outline-none focus:border-dars-terra transition-colors"
                  placeholder="Acme EdTech Ltd."
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-dars-ink tracking-wide uppercase" htmlFor="su-email">
                  Email
                </label>
                <input
                  id="su-email"
                  type="email"
                  required
                  value={suEmail}
                  onChange={(e) => setSuEmail(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-dars-rule-light rounded-md bg-dars-parchment text-dars-ink placeholder:text-dars-muted-light focus:outline-none focus:border-dars-terra transition-colors"
                  placeholder="you@yourorg.com"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-dars-ink tracking-wide uppercase" htmlFor="su-password">
                  Password
                </label>
                <input
                  id="su-password"
                  type="password"
                  required
                  value={suPassword}
                  onChange={(e) => setSuPassword(e.target.value)}
                  className="w-full px-3 py-2.5 text-sm border border-dars-rule-light rounded-md bg-dars-parchment text-dars-ink placeholder:text-dars-muted-light focus:outline-none focus:border-dars-terra transition-colors"
                  placeholder="••••••••"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-dars-terra text-white py-2.5 rounded-md text-sm font-semibold hover:opacity-90 transition-opacity disabled:opacity-50 cursor-pointer"
              >
                {loading ? "Creating account…" : "Create Account"}
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Footer nav */}
      <p className="mt-6 text-xs text-dars-muted">
        {tab === "signin" ? (
          <>No account?{" "}
            <button onClick={() => switchTab("signup")} className="text-dars-terra underline cursor-pointer bg-transparent border-none p-0">
              Sign up
            </button>
          </>
        ) : (
          <>Already have an account?{" "}
            <button onClick={() => switchTab("signin")} className="text-dars-terra underline cursor-pointer bg-transparent border-none p-0">
              Sign in
            </button>
          </>
        )}
      </p>
    </main>
  );
}
