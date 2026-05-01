"use client";

import { useState } from "react";
import { Logo } from "@/components/atoms/logo";

const DEMO_EMAIL = "dars@taleemabad.com";
const DEMO_PASSWORD = "dars123";

const DEMO_SESSION = {
  api_key: "demo",
  client_id: "demo",
  name: "Taleemabad Demo",
  email: DEMO_EMAIL,
  teacher_id: "demo",
  is_admin: false,
};

export function LoginTemplate() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [signedIn, setSignedIn] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (email === DEMO_EMAIL && password === DEMO_PASSWORD) {
      localStorage.setItem("dars_session", JSON.stringify(DEMO_SESSION));
      setSignedIn(true);
    } else {
      setError("Invalid email or password.");
    }
  }

  if (signedIn) {
    return (
      <main className="min-h-screen bg-dars-parchment flex flex-col items-center justify-center px-4 py-16">
        <a href="/" className="no-underline mb-10">
          <Logo size="md" />
        </a>
        <div className="w-full max-w-sm bg-white border border-dars-rule-light rounded-xl px-8 py-8 space-y-5">
          <h1 className="font-serif text-xl font-bold text-dars-ink">Choose dashboard</h1>
          <p className="text-sm text-dars-muted">Which dashboard would you like to open?</p>
          <div className="space-y-3">
            <a
              href="/dashboard"
              className="flex flex-col px-4 py-3.5 rounded-lg border border-dars-rule-dark hover:border-dars-terra hover:bg-dars-parchment transition-colors no-underline group"
            >
              <span className="text-sm font-semibold text-dars-ink group-hover:text-dars-terra">Simple Dashboard</span>
              <span className="text-xs text-dars-muted mt-0.5">Lesson plans, analytics, teachers, curriculum</span>
            </a>
            <a
              href="/dashboard-pef"
              className="flex flex-col px-4 py-3.5 rounded-lg border border-dars-rule-dark hover:border-dars-terra hover:bg-dars-parchment transition-colors no-underline group"
            >
              <span className="text-sm font-semibold text-dars-ink group-hover:text-dars-terra">PEF Dashboard</span>
              <span className="text-xs text-dars-muted mt-0.5">Lesson plans and exam generator</span>
            </a>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-dars-parchment flex flex-col items-center justify-center px-4 py-16">
      <a href="/" className="no-underline mb-10">
        <Logo size="md" />
      </a>
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm bg-white border border-dars-rule-light rounded-xl px-8 py-8 space-y-5"
      >
        <h1 className="font-serif text-xl font-bold text-dars-ink">Sign in</h1>

        <div>
          <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
            placeholder="you@example.com"
          />
        </div>

        <div>
          <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">Password</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
            placeholder="••••••••"
          />
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          className="w-full py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none"
        >
          Sign in
        </button>
      </form>
    </main>
  );
}
