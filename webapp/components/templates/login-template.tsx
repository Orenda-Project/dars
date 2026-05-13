"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Logo } from "@/components/atoms/logo";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

const inputClass =
  "w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra";
const labelClass =
  "block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide";

export function LoginTemplate() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "signup" | "key-reveal">("signin");

  // sign-in state
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");

  // sign-up state
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [curriculum, setCurriculum] = useState("NCP");
  const [newApiKey, setNewApiKey] = useState("");
  const [copied, setCopied] = useState(false);

  const [loading, setLoading] = useState(false);

  async function handleSignIn(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: signInEmail.trim(), password: signInPassword }),
      });
      const text = await res.text();
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(text); } catch { throw new Error(`Server returned unexpected response (HTTP ${res.status}). Is NEXT_PUBLIC_API_URL set correctly?`); }
      if (!res.ok) throw new Error((data.detail as string) ?? `HTTP ${res.status}`);
      localStorage.setItem("dars_pef_session", JSON.stringify({
        api_key: data.api_key,
        client_id: data.client_id,
        name: data.name,
        email: data.email,
        is_admin: data.is_admin,
      }));
      router.push("/dashboard/lesson-plans");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Sign in failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password, curriculum }),
      });
      const text = await res.text();
      let data: Record<string, unknown> = {};
      try { data = JSON.parse(text); } catch { throw new Error(`Server returned unexpected response (HTTP ${res.status}). Is NEXT_PUBLIC_API_URL set correctly?`); }
      if (!res.ok) throw new Error((data.detail as string) ?? `HTTP ${res.status}`);
      setNewApiKey(data.api_key as string);
      setMode("key-reveal");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Signup failed.");
    } finally {
      setLoading(false);
    }
  }

  function handleContinue() {
    localStorage.setItem("dars_pef_session", JSON.stringify({ api_key: newApiKey, is_admin: false }));
    router.push("/dashboard/lesson-plans");
  }

  async function handleCopy() {
    await navigator.clipboard.writeText(newApiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <main className="min-h-screen bg-dars-parchment flex flex-col items-center justify-center px-4 py-16">
      <a href="/" className="no-underline mb-10">
        <Logo size="md" />
      </a>

      {/* ── Sign in ── */}
      {mode === "signin" && (
        <form
          onSubmit={handleSignIn}
          className="w-full max-w-sm bg-white border border-dars-rule-light rounded-xl px-8 py-8 space-y-5"
        >
          <h1 className="font-serif text-xl font-bold text-dars-ink">Dars Dashboard</h1>
          <p className="text-sm text-dars-muted -mt-1">Sign in with your email and password.</p>

          <div>
            <label className={labelClass}>Email</label>
            <input
              type="email"
              required
              value={signInEmail}
              onChange={(e) => setSignInEmail(e.target.value)}
              className={inputClass}
              placeholder="you@example.com"
            />
          </div>

          <div>
            <label className={labelClass}>Password</label>
            <input
              type="password"
              required
              value={signInPassword}
              onChange={(e) => setSignInPassword(e.target.value)}
              className={inputClass}
              placeholder="••••••••"
            />
          </div>

          <button type="submit" disabled={loading} className="w-full py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-50">
            {loading ? "Signing in…" : "Sign in"}
          </button>

          <p className="text-center text-xs text-dars-muted">
            No account?{" "}
            <button type="button" onClick={() => { setMode("signup"); }} className="text-dars-terra underline bg-transparent border-none cursor-pointer p-0">
              Create one
            </button>
          </p>
        </form>
      )}

      {/* ── Sign up ── */}
      {mode === "signup" && (
        <form
          onSubmit={handleSignUp}
          className="w-full max-w-sm bg-white border border-dars-rule-light rounded-xl px-8 py-8 space-y-5"
        >
          <h1 className="font-serif text-xl font-bold text-dars-ink">Create account</h1>

          <div>
            <label className={labelClass}>Organisation name</label>
            <input type="text" required value={name} onChange={(e) => setName(e.target.value)} className={inputClass} placeholder="e.g. PEF" />
          </div>
          <div>
            <label className={labelClass}>Email</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="you@example.com" />
          </div>
          <div>
            <label className={labelClass}>Password</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} className={inputClass} placeholder="••••••••" />
          </div>

          <div>
            <label className={labelClass}>Curriculum</label>
            <select required value={curriculum} onChange={(e) => setCurriculum(e.target.value)} className={inputClass}>
              <option value="NCP">National Curriculum of Pakistan (NCP)</option>
              <option value="SNC">Single National Curriculum (SNC)</option>
            </select>
            <p className="text-xs text-dars-muted mt-1">This cannot be changed after signup.</p>
          </div>

          <button type="submit" disabled={loading} className="w-full py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-50">
            {loading ? "Creating…" : "Create account"}
          </button>

          <p className="text-center text-xs text-dars-muted">
            Already have an account?{" "}
            <button type="button" onClick={() => { setMode("signin"); }} className="text-dars-terra underline bg-transparent border-none cursor-pointer p-0">
              Sign in
            </button>
          </p>
        </form>
      )}

      {/* ── API key reveal ── */}
      {mode === "key-reveal" && (
        <div className="w-full max-w-sm bg-white border border-dars-rule-light rounded-xl px-8 py-8 space-y-5">
          <h1 className="font-serif text-xl font-bold text-dars-ink">Your API key</h1>
          <p className="text-sm text-dars-muted">Copy it now or find it later in Settings.</p>

          <div className="flex items-center gap-2">
            <code className="flex-1 bg-dars-parchment border border-dars-rule-light rounded-md px-3 py-2 text-xs text-dars-ink break-all">
              {newApiKey}
            </code>
            <button
              onClick={handleCopy}
              className="shrink-0 px-3 py-2 text-xs font-semibold border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment transition-colors cursor-pointer bg-white"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
          </div>

          <button onClick={handleContinue} className="w-full py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none">
            Continue to dashboard
          </button>
        </div>
      )}
    </main>
  );
}
