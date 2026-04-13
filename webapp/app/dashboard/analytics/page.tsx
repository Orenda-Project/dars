"use client";

import { useEffect, useState } from "react";

interface Session {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
}

interface StatsState {
  total: number | null;
  loading: boolean;
  error: string | null;
}

export default function AnalyticsPage() {
  const [session, setSession] = useState<Session | null>(null);
  const [stats, setStats] = useState<StatsState>({ total: null, loading: true, error: null });

  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  useEffect(() => {
    const raw = localStorage.getItem("dars_session");
    if (!raw) {
      window.location.href = "/login";
      return;
    }
    const s = JSON.parse(raw) as Session;
    setSession(s);

    fetch(`${apiBase}/api/v1/lesson-plans?limit=1&offset=0`, {
      headers: { "X-API-Key": s.api_key },
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem("dars_session");
            window.location.href = "/login";
            return;
          }
          throw new Error("Failed to fetch stats.");
        }
        const data = await res.json();
        setStats({ total: data.total as number, loading: false, error: null });
      })
      .catch((err: unknown) => {
        setStats({
          total: null,
          loading: false,
          error: err instanceof Error ? err.message : "An unexpected error occurred.",
        });
      });
  }, [apiBase]);

  return (
    <div className="p-8 max-w-2xl">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-serif font-bold text-dars-ink">Analytics</h1>
        {session && (
          <p className="text-sm text-dars-muted mt-1">
            {session.name} &middot; {session.email}
          </p>
        )}
      </div>

      {/* Stat card */}
      <div className="border border-dars-rule-light rounded-lg bg-dars-parchment p-6 flex flex-col gap-2 w-64">
        <p className="text-xs font-semibold text-dars-muted tracking-wide uppercase">
          Total Lesson Plans Generated
        </p>

        {stats.loading && (
          <p className="text-3xl font-serif font-bold text-dars-ink animate-pulse">—</p>
        )}

        {stats.error && (
          <p className="text-sm text-red-600">{stats.error}</p>
        )}

        {!stats.loading && stats.total !== null && (
          <p className="text-4xl font-serif font-bold text-dars-terra">
            {stats.total.toLocaleString()}
          </p>
        )}
      </div>
    </div>
  );
}
