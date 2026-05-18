/**
 * F4.3 — API key setup page template.
 *
 * Shown when a user lands in /teacher-app/* without a key. Stateless
 * template; the page wires the localStorage write.
 */
"use client";

import { useState } from "react";

interface SetupTemplateProps {
  onSubmit: (apiKey: string) => Promise<void>;
  initialKey?: string;
}

export function TeacherAppSetupTemplate({
  onSubmit,
  initialKey = "",
}: SetupTemplateProps) {
  const [apiKey, setApiKey] = useState(initialKey);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSubmit(apiKey.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save key");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-dars-parchment flex items-center justify-center px-4">
      <div className="max-w-md w-full">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-2">
          Sample teacher app — set up
        </h1>
        <p className="text-sm text-dars-muted mb-6">
          Paste your Dars org API key below to load this sample teacher
          experience. The key stays in your browser; this app makes no
          server calls of its own.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-dars-ink-soft">
              API key
            </span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="dk_..."
              autoComplete="off"
              spellCheck={false}
              className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-dars-ink font-mono text-sm focus:outline-none focus:ring-2 focus:ring-dars-terra focus:border-dars-terra"
            />
          </label>

          {error ? (
            <p className="text-sm text-dars-terra" role="alert">
              {error}
            </p>
          ) : null}

          <button
            type="submit"
            disabled={busy || !apiKey.trim()}
            className="w-full px-4 py-2.5 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold disabled:opacity-50 hover:opacity-90 transition-opacity"
          >
            {busy ? "Saving…" : "Continue →"}
          </button>
        </form>

        <p className="text-xs text-dars-muted-light mt-6">
          The demo key for staging is{" "}
          <code className="font-mono">dk_demo_dars_eng_g1_2dc7e0b8408142fa</code>
          .
        </p>
      </div>
    </div>
  );
}
