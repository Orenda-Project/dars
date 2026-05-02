"use client";

import { useState, useEffect } from "react";
import { getApiKey, getSession } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

export default function SettingsPage() {
  const [apiKey, setApiKey] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [session, setSession] = useState<{ name?: string; email?: string } | null>(null);

  useEffect(() => {
    const s = getSession();
    setSession(s);
    setApiKey(getSession()?.api_key ?? "");
  }, []);

  async function handleCopy() {
    await navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function handleRotate() {
    if (!confirm("This will invalidate your current API key. Continue?")) return;
    setRotating(true);
    try {
      const res = await fetch(`${API_URL}/api/v1/me/rotate-key`, {
        method: "POST",
        headers: { "X-API-Key": apiKey },
      });
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      const raw = localStorage.getItem("dars_pef_session");
      if (raw) {
        const parsed = JSON.parse(raw);
        parsed.api_key = data.api_key;
        localStorage.setItem("dars_pef_session", JSON.stringify(parsed));
      }
      setApiKey(data.api_key);
      setRevealed(true);
    } catch {
      alert("Failed to rotate key. Try again.");
    } finally {
      setRotating(false);
    }
  }

  const masked = apiKey ? apiKey.slice(0, 8) + "••••••••••••••••••••••••••••••••" : "";

  return (
    <div className="p-8 max-w-xl">
      <h1 className="font-serif text-2xl font-bold text-dars-ink mb-8">Settings</h1>

      {session && (
        <div className="mb-8 pb-8 border-b border-dars-rule-light">
          <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-3">Account</p>
          <div className="space-y-1">
            {session.name && <p className="text-sm text-dars-ink font-medium">{session.name}</p>}
            {session.email && <p className="text-sm text-dars-muted">{session.email}</p>}
          </div>
        </div>
      )}

      <div>
        <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-3">API Key</p>
        <p className="text-xs text-dars-muted mb-4">
          Use this key in the <code className="bg-dars-parchment px-1 py-0.5 rounded text-dars-ink">X-API-Key</code> header when calling the Dars API from your application.
        </p>

        <div className="flex items-center gap-2 mb-4">
          <code className="flex-1 bg-dars-parchment border border-dars-rule-light rounded-md px-3 py-2 text-xs text-dars-ink break-all font-mono">
            {revealed ? apiKey : masked}
          </code>
          <button
            onClick={() => setRevealed((r) => !r)}
            className="shrink-0 px-3 py-2 text-xs font-semibold border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment transition-colors cursor-pointer bg-white"
          >
            {revealed ? "Hide" : "Reveal"}
          </button>
          <button
            onClick={handleCopy}
            className="shrink-0 px-3 py-2 text-xs font-semibold border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment transition-colors cursor-pointer bg-white"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
        </div>

        <button
          onClick={handleRotate}
          disabled={rotating}
          className="px-4 py-2 text-xs font-semibold border border-dars-rule-dark rounded-md text-dars-muted hover:text-red-600 hover:border-red-300 transition-colors cursor-pointer bg-white disabled:opacity-50"
        >
          {rotating ? "Rotating…" : "Rotate key"}
        </button>
        <p className="text-xs text-dars-muted mt-2">Rotating generates a new key and immediately invalidates the old one.</p>
      </div>
    </div>
  );
}
