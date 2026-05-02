"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface LessonPlan {
  id: string;
  grade: string;
  subject: string;
  curriculum: string;
  status: "PENDING" | "READY" | "ERROR" | string;
  created_at: string;
  content?: string | null;
}

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return "";
  try { return JSON.parse(raw).api_key ?? ""; } catch { return ""; }
}

const CURRICULUM_SUBJECTS: Record<string, Record<string, number[]>> = {
  ICT:    { Eng: [1,2,3,4,5], Maths: [1,2,3,4,5], Urdu: [1,2,3,4,5], Science: [4,5] },
  Punjab: { Eng: [1,2,3,4,5], Maths: [1,2,3,4,5], Urdu: [1,2,3,4,5] },
  Sindh:  { Eng: [1,2,3,4,5], Maths: [1,2,3,4,5], Urdu: [1,2,3,4,5], Science: [5], GK: [1,2] },
};

function NoCurriculumBanner() {
  return (
    <div className="mb-6 flex items-start gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
      <span className="mt-0.5 text-amber-500 shrink-0">⚠</span>
      <span>
        Your account has no curriculum configured. Lesson plan generation requires a curriculum.{" "}
        <Link href="/dashboard/settings" className="font-semibold underline underline-offset-2 hover:text-amber-900">
          Go to Settings to select ICT or Punjab.
        </Link>
      </span>
    </div>
  );
}

function GenerateForm({ curriculum, onGenerated }: { curriculum: string; onGenerated: (lp: LessonPlan) => void }) {
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [pageNumber, setPageNumber] = useState("");
  const [topic, setTopic] = useState("");
  const [classStrength, setClassStrength] = useState("");
  const [generateBilingual, setGenerateBilingual] = useState(false);
  const [loading, setLoading] = useState(false);

  const subjects = Object.keys(CURRICULUM_SUBJECTS[curriculum] ?? {});
  const grades = subject ? (CURRICULUM_SUBJECTS[curriculum]?.[subject] ?? []) : [];

  function handleSubjectChange(val: string) { setSubject(val); setGrade(""); }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const body: Record<string, unknown> = {
      grade: Number(grade), subject, page_number: pageNumber, generate_bilingual: generateBilingual,
    };
    if (topic.trim()) body.topic = topic.trim();
    if (classStrength.trim()) body.class_strength = Number(classStrength);
    try {
      const res = await fetch(`${API_URL}/api/v1/custom-lesson-plans`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": getApiKey() },
        body: JSON.stringify(body),
      });
      if (!res.ok) { const t = await res.text(); throw new Error(t || `HTTP ${res.status}`); }
      onGenerated(await res.json());
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Unknown error");
    } finally { setLoading(false); }
  }

  const sel = "w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra";
  const lbl = "block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide";

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8 shadow-sm">
      <h2 className="font-serif text-lg font-bold text-dars-ink mb-4 flex items-center gap-2 before:content-[''] before:block before:w-1 before:h-5 before:bg-dars-terra before:rounded-full">Generate Lesson Plan</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={lbl}>Subject *</label>
            <select required value={subject} onChange={(e) => handleSubjectChange(e.target.value)} className={sel}>
              <option value="">Select subject</option>
              {subjects.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className={lbl}>Grade *</label>
            <select required value={grade} onChange={(e) => setGrade(e.target.value)} className={sel} disabled={!subject}>
              <option value="">Select grade</option>
              {grades.map((g) => <option key={g} value={g}>Grade {g}</option>)}
            </select>
          </div>
          <div>
            <label className={lbl}>Page Number *</label>
            <input type="text" required value={pageNumber} onChange={(e) => setPageNumber(e.target.value)} className={sel} placeholder="e.g. 42" />
          </div>
          <div>
            <label className={lbl}>Class Strength</label>
            <input type="number" min={1} value={classStrength} onChange={(e) => setClassStrength(e.target.value)} className={sel} placeholder="Optional" />
          </div>
          <div className="sm:col-span-2">
            <label className={lbl}>Topic</label>
            <input type="text" value={topic} onChange={(e) => setTopic(e.target.value)} className={sel} placeholder="Optional" />
          </div>
        </div>
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" checked={generateBilingual} onChange={(e) => setGenerateBilingual(e.target.checked)} className="accent-dars-terra w-4 h-4" />
          <span className="text-sm text-dars-ink">Generate Bilingual</span>
        </label>
        <button type="submit" disabled={loading} className="px-5 py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-50 disabled:cursor-not-allowed">
          {loading ? "Generating…" : "Generate"}
        </button>
      </form>
    </section>
  );
}

function GenerationResult({ initial }: { initial: LessonPlan }) {
  const [lp, setLp] = useState<LessonPlan>(initial);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef(Date.now());

  const stopPolling = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/custom-lesson-plans/${initial.id}`, { headers: { "X-API-Key": getApiKey() } });
      if (!res.ok) return;
      const data: LessonPlan = await res.json();
      setLp(data);
      if (data.status === "READY" || data.status === "ERROR") stopPolling();
      if (Date.now() - startedAt.current > 120_000) stopPolling();
    } catch { /* silent */ }
  }, [initial.id, stopPolling]);

  useEffect(() => {
    if (lp.status !== "READY" && lp.status !== "ERROR") intervalRef.current = setInterval(fetchStatus, 3000);
    return stopPolling;
  }, [fetchStatus, stopPolling, lp.status]);

  const statusColor = lp.status === "READY" ? "text-emerald-700 bg-emerald-50 border-emerald-200"
    : lp.status === "ERROR" ? "text-red-700 bg-red-50 border-red-200"
    : "text-dars-muted bg-dars-parchment border-dars-rule-light";

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="font-serif text-lg font-bold text-dars-ink">Latest Generation</h2>
        <span className={`text-xs font-semibold uppercase tracking-wide border rounded px-2 py-0.5 ${statusColor}`}>{lp.status}</span>
      </div>
      <p className="text-xs text-dars-muted mb-1">ID: <span className="font-mono">{lp.id}</span></p>
      {lp.status !== "READY" && lp.status !== "ERROR" && <p className="text-sm text-dars-muted mt-2 animate-pulse">Polling for result…</p>}
      {lp.status === "ERROR" && <p className="text-sm text-red-600 mt-2">Generation failed. Please try again.</p>}
      {lp.status === "READY" && lp.content && (
        <div className="mt-4 prose prose-sm max-w-none border-t border-dars-rule-light pt-4" dangerouslySetInnerHTML={{ __html: lp.content }} />
      )}
      {lp.status === "READY" && !lp.content && <p className="text-sm text-dars-muted mt-2">No content returned.</p>}
    </section>
  );
}

export default function LessonPlansPage() {
  const [latestLp, setLatestLp] = useState<LessonPlan | null>(null);
  const [curriculum, setCurriculum] = useState<string | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);

  useEffect(() => {
    const raw = localStorage.getItem("dars_pef_session");
    const key = raw ? (JSON.parse(raw).api_key ?? "") : "";
    if (!key) { setLoadingProfile(false); return; }
    fetch(`${API_URL}/api/v1/me`, { headers: { "X-API-Key": key } })
      .then((r) => r.ok ? r.json() : null)
      .then((d) => { if (d) setCurriculum(d.curriculum ?? null); })
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, []);

  return (
    <div className="px-8 py-8 max-w-4xl">
      <div className="mb-8 pb-6 border-b border-dars-rule-light">
        <h1 className="font-serif text-2xl font-bold text-dars-ink">Lesson Plans</h1>
        <p className="text-sm text-dars-muted mt-1">Generate and manage curriculum-aligned lesson plans.</p>
      </div>
      {!loadingProfile && !curriculum && <NoCurriculumBanner />}
      {curriculum ? (
        <GenerateForm curriculum={curriculum} onGenerated={setLatestLp} />
      ) : (
        !loadingProfile && (
          <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8 shadow-sm">
            <p className="text-sm text-dars-muted">Set your curriculum in Settings to generate lesson plans.</p>
          </section>
        )
      )}
      {latestLp && <GenerationResult key={latestLp.id} initial={latestLp} />}
    </div>
  );
}
