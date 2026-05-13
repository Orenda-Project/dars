"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getExam, type GeneratedExamResponse } from "@/lib/school-api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return "";
  try { return JSON.parse(raw).api_key ?? ""; } catch { return ""; }
}

// ---------------------------------------------------------------------------
// Exam result + polling
// ---------------------------------------------------------------------------

function ExamResult({ examId }: { examId: string }) {
  const [exam, setExam] = useState<GeneratedExamResponse | null>(null);
  const [slideOpen, setSlideOpen] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
  }, []);

  const fetchExam = useCallback(async () => {
    try {
      const data = await getExam(examId);
      setExam(data);
      if (data.status === "READY" || data.status === "ERROR") stopPolling();
    } catch { /* silent */ }
  }, [examId, stopPolling]);

  useEffect(() => {
    fetchExam();
    intervalRef.current = setInterval(fetchExam, 3000);
    return stopPolling;
  }, [fetchExam, stopPolling]);

  if (!exam) return <p className="text-sm text-gray-400 animate-pulse">Waiting for result…</p>;

  const statusColors: Record<string, string> = {
    READY: "bg-green-100 text-green-700 border-green-200",
    ERROR: "bg-red-100 text-red-700 border-red-200",
    PENDING: "bg-amber-50 text-amber-700 border-amber-200",
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-5">
      <div className="flex items-center gap-3 mb-3">
        <h3 className="font-semibold text-gray-900 text-sm">Result</h3>
        <span className={`text-xs font-semibold uppercase tracking-wide border rounded px-2 py-0.5 ${statusColors[exam.status] ?? statusColors.PENDING}`}>
          {exam.status}
        </span>
      </div>
      <p className="text-xs text-gray-400 mb-3 font-mono">{exam.id}</p>

      {exam.status === "PENDING" && (
        <p className="text-sm text-amber-600 animate-pulse">Generating exam…</p>
      )}
      {exam.status === "ERROR" && (
        <p className="text-sm text-red-600">{exam.error_message ?? "Generation failed."}</p>
      )}
      {exam.status === "READY" && (
        <button
          onClick={() => setSlideOpen(true)}
          className="text-sm px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors border-none cursor-pointer font-medium"
        >
          View Exam
        </button>
      )}

      {/* Slide-over */}
      {slideOpen && exam.status === "READY" && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setSlideOpen(false)} />
          <div className="relative w-full max-w-2xl bg-white h-full shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
              <h2 className="font-semibold text-gray-900 text-sm">Exam Result</h2>
              <button onClick={() => setSlideOpen(false)} className="text-gray-400 hover:text-gray-600 bg-transparent border-none cursor-pointer p-1">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              <pre className="text-xs bg-gray-50 p-4 rounded overflow-auto whitespace-pre-wrap">
                {JSON.stringify(exam.result, null, 2)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Generate form
// ---------------------------------------------------------------------------

interface GradeOption { code: number; display_name: string; }
interface SubjectOption { code: string; display_name: string; }

export default function QuickExamPage() {
  const [grades, setGrades] = useState<GradeOption[]>([]);
  const [subjects, setSubjects] = useState<SubjectOption[]>([]);
  const [grade, setGrade] = useState("");
  const [subject, setSubject] = useState("");
  const [pageRanges, setPageRanges] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const [resultKey, setResultKey] = useState(0);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/grades`).then((r) => r.json()).then(setGrades).catch(() => {});
    fetch(`${API_URL}/api/v1/subjects`).then((r) => r.json()).then(setSubjects).catch(() => {});
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const body = {
      grade: Number(grade),
      subject,
      page_ranges: pageRanges,
      generation_type: "exam",
      question_types: ["unseen"],
    };
    try {
      const res = await fetch(`${API_URL}/api/v1/exams`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": getApiKey() },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const d = await res.json() as { detail?: string }; if (d.detail) msg = String(d.detail); } catch { /* ignore */ }
        throw new Error(msg);
      }
      const data = await res.json() as { id: string };
      setResultId(data.id);
      setResultKey((k) => k + 1);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  const sel = "w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-violet-500";
  const lbl = "block text-xs font-semibold text-gray-500 mb-1 uppercase tracking-wide";

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-xl font-semibold text-gray-900">Quick Exam</h1>
        <p className="text-sm text-gray-500 mt-1">Generate a freehand exam for any page range.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 mb-6">
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className={lbl}>Subject *</label>
              <select required value={subject} onChange={(e) => setSubject(e.target.value)} className={sel}>
                <option value="">Select subject</option>
                {subjects.map((s) => (
                  <option key={s.code} value={s.code}>{s.display_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className={lbl}>Grade *</label>
              <select required value={grade} onChange={(e) => setGrade(e.target.value)} className={sel}>
                <option value="">Select grade</option>
                {grades.map((g) => (
                  <option key={g.code} value={g.code}>{g.display_name}</option>
                ))}
              </select>
            </div>
            <div className="sm:col-span-2">
              <label className={lbl}>Page Ranges *</label>
              <input
                type="text"
                required
                value={pageRanges}
                onChange={(e) => setPageRanges(e.target.value)}
                className={sel}
                placeholder="e.g. 1-10,15-20"
              />
              <p className="text-xs text-gray-400 mt-1">Comma-separated page ranges from the textbook.</p>
            </div>
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="px-5 py-2.5 bg-violet-600 text-white text-sm font-semibold rounded-lg hover:bg-violet-700 transition-colors cursor-pointer border-none disabled:opacity-50"
          >
            {loading ? "Generating…" : "Generate Exam"}
          </button>
        </form>
      </div>

      {resultId && <ExamResult key={resultKey} examId={resultId} />}
    </div>
  );
}
