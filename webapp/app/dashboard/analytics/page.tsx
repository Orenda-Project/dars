"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return "";
  try { return JSON.parse(raw).api_key ?? ""; } catch { return ""; }
}

interface StatusCounts { pending: number; ready: number; error: number; }
interface SubjectCount { subject: string; count: number; }
interface GradeCount { grade: string; count: number; }
interface DailyCount { date: string; count: number; }

interface SectionAnalytics {
  total: number;
  by_status: StatusCounts;
  by_subject: SubjectCount[];
  by_grade: GradeCount[];
  daily_last_30: DailyCount[];
}

interface AnalyticsData {
  lesson_plans: SectionAnalytics;
  exam_generations: SectionAnalytics;
}

const SUBJECT_DISPLAY: Record<string, string> = {
  Eng: "English", Maths: "Mathematics", Urdu: "Urdu",
  Islamiat: "Islamiat", GenSci: "Science", GenK: "General Knowledge", SST: "Social Studies",
};

// ─── Stat card ────────────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-white border border-dars-rule-light rounded-xl p-5 shadow-sm">
      <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-1">{label}</p>
      <p className="text-3xl font-bold text-dars-ink font-serif">{value}</p>
      {sub && <p className="text-xs text-dars-muted mt-1">{sub}</p>}
    </div>
  );
}

// ─── Horizontal bar chart ─────────────────────────────────────────────────────

function BarChart({ items, label }: { items: { label: string; count: number }[]; label: string }) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div>
      <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-3">{label}</p>
      <div className="space-y-2">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-3">
            <span className="text-xs text-dars-ink w-28 shrink-0 truncate">{item.label}</span>
            <div className="flex-1 bg-dars-parchment rounded-full h-2 overflow-hidden">
              <div
                className="h-2 bg-dars-terra rounded-full transition-all"
                style={{ width: `${(item.count / max) * 100}%` }}
              />
            </div>
            <span className="text-xs text-dars-muted w-8 text-right shrink-0">{item.count}</span>
          </div>
        ))}
        {items.length === 0 && <p className="text-xs text-dars-muted">No data.</p>}
      </div>
    </div>
  );
}

// ─── Sparkline / activity chart ───────────────────────────────────────────────

function ActivityChart({ daily }: { daily: DailyCount[] }) {
  if (daily.length === 0) {
    return <p className="text-xs text-dars-muted">No activity in the last 30 days.</p>;
  }

  // Build a full 30-day map
  const today = new Date();
  const buckets: { date: string; count: number }[] = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    buckets.push({ date: key, count: 0 });
  }
  for (const row of daily) {
    const bucket = buckets.find((b) => b.date === row.date);
    if (bucket) bucket.count = row.count;
  }

  const maxCount = Math.max(...buckets.map((b) => b.count), 1);

  return (
    <div>
      <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-3">Activity — last 30 days</p>
      <div className="flex items-end gap-0.5 h-16">
        {buckets.map((b) => (
          <div key={b.date} className="flex-1 flex flex-col items-center justify-end h-full group relative">
            <div
              className="w-full bg-dars-terra/70 rounded-sm hover:bg-dars-terra transition-colors"
              style={{ height: `${Math.max((b.count / maxCount) * 100, b.count > 0 ? 8 : 2)}%` }}
            />
            {b.count > 0 && (
              <span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] text-dars-ink bg-white border border-dars-rule-light rounded px-1 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                {b.date.slice(5)}: {b.count}
              </span>
            )}
          </div>
        ))}
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[10px] text-dars-muted">30d ago</span>
        <span className="text-[10px] text-dars-muted">Today</span>
      </div>
    </div>
  );
}

// ─── Section panel ────────────────────────────────────────────────────────────

function AnalyticsSection({ title, data }: { title: string; data: SectionAnalytics }) {
  const subjectItems = data.by_subject.map((s) => ({
    label: SUBJECT_DISPLAY[s.subject] ?? s.subject,
    count: s.count,
  }));
  const gradeItems = data.by_grade.map((g) => ({ label: `Grade ${g.grade}`, count: g.count }));

  const successRate = data.total > 0
    ? Math.round((data.by_status.ready / data.total) * 100)
    : null;

  return (
    <div className="bg-white border border-dars-rule-light rounded-xl shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-dars-rule-light flex items-center gap-2">
        <h2 className="font-serif text-lg font-bold text-dars-ink flex items-center gap-2 before:content-[''] before:block before:w-1 before:h-5 before:bg-dars-terra before:rounded-full">
          {title}
        </h2>
      </div>
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard label="Total" value={data.total} />
          <StatCard label="Ready" value={data.by_status.ready} sub={successRate !== null ? `${successRate}% success` : undefined} />
          <StatCard label="Pending" value={data.by_status.pending} />
          <StatCard label="Error" value={data.by_status.error} />
        </div>

        <ActivityChart daily={data.daily_last_30} />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
          <BarChart items={subjectItems} label="By Subject" />
          <BarChart items={gradeItems} label="By Grade" />
        </div>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const key = getApiKey();
    if (!key) { setLoading(false); setError("Not authenticated."); return; }
    fetch(`${API_URL}/api/v1/analytics`, { headers: { "X-API-Key": key } })
      .then((r) => r.ok ? r.json() : r.text().then((t) => Promise.reject(t)))
      .then((d) => setData(d))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="px-8 py-8 max-w-5xl">
      <div className="mb-8 pb-6 border-b border-dars-rule-light">
        <h1 className="font-serif text-2xl font-bold text-dars-ink">Analytics</h1>
        <p className="text-sm text-dars-muted mt-1">Aggregated stats for your custom lesson plans and exam generations.</p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-dars-muted">
          <span className="animate-pulse">Loading analytics…</span>
        </div>
      )}

      {error && (
        <div className="px-4 py-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          Failed to load analytics: {error}
        </div>
      )}

      {data && (
        <div className="space-y-8">
          <AnalyticsSection title="Lesson Plans" data={data.lesson_plans} />
          <AnalyticsSection title="Exam Generations" data={data.exam_generations} />
        </div>
      )}
    </div>
  );
}
