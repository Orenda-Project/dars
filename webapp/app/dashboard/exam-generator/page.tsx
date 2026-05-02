"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface ExamGeneration {
  id: string;
  curriculum: string;
  grade: string | number;
  subject: string;
  status: "PENDING" | "READY" | "ERROR" | string;
  created_at: string;
  result?: unknown | null;
}

interface PaginatedResponse {
  items: ExamGeneration[];
  total: number;
  limit: number;
  offset: number;
}

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return "";
  try {
    return JSON.parse(raw).api_key ?? "";
  } catch {
    return "";
  }
}

// ─── Curriculum data (from UG_EG config.py) ──────────────────────────────────

const CURRICULUM_DATA: Record<string, Record<string, number[]>> = {
  ICT: {
    Eng:      [1, 2, 3, 4, 5],
    Maths:    [1, 2, 3, 4, 5],
    Urdu:     [1, 2, 3, 4, 5],
    Islamiat: [1, 2, 3, 4, 5],
    GenSci:   [4, 5],
    GenK:     [1, 2, 3],
    SST:      [4, 5],
  },
  Punjab: {
    Eng:   [1, 2, 3, 4, 5],
    Maths: [1, 2, 3, 4, 5],
    Urdu:  [1, 2, 3, 4, 5],
  },
};

const SUBJECT_DISPLAY: Record<string, string> = {
  Eng:      "English",
  Maths:    "Mathematics",
  Urdu:     "Urdu",
  Islamiat: "Islamiat",
  GenSci:   "Science",
  GenK:     "General Knowledge",
  SST:      "Social Studies",
};

const GENERATION_TYPES = [
  { value: "exam", label: "Exam" },
  { value: "class_assessment", label: "Class Assessment" },
];

// ─── Generate Form ────────────────────────────────────────────────────────────

function GenerateForm({ onGenerated }: { onGenerated: (eg: ExamGeneration) => void }) {
  const [curriculum, setCurriculum] = useState("ICT");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [pageRanges, setPageRanges] = useState("");
  const [generationType, setGenerationType] = useState("exam");
  const [includeAnswerKey, setIncludeAnswerKey] = useState(false);
  const [loading, setLoading] = useState(false);

  const subjects = Object.keys(CURRICULUM_DATA[curriculum] ?? {});
  const grades = subject ? (CURRICULUM_DATA[curriculum]?.[subject] ?? []) : [];

  function handleCurriculumChange(val: string) {
    setCurriculum(val);
    setSubject("");
    setGrade("");
  }
  function handleSubjectChange(val: string) {
    setSubject(val);
    setGrade("");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    const apiKey = getApiKey();

    const body = {
      curriculum,
      subject,
      grade: Number(grade),
      page_ranges: pageRanges,
      generation_type: generationType,
      include_answer_key: includeAnswerKey,
      // fixed backend defaults
      question_types: ["seen", "unseen"],
      seen_categories: ["objective", "subjective"],
      unseen_categories: ["objective", "subjective"],
      image_generation_enabled: false,
      enable_review: false,
    };

    try {
      const res = await fetch(`${API_URL}/api/v1/custom-exam-generations`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": apiKey,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      const eg: ExamGeneration = await res.json();
      onGenerated(eg);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  const selectClass =
    "w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra";
  const inputClass = selectClass;
  const labelClass = "block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide";

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8">
      <h2 className="font-serif text-lg font-bold text-dars-ink mb-4">Generate Exam</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Curriculum *</label>
            <select
              required
              value={curriculum}
              onChange={(e) => handleCurriculumChange(e.target.value)}
              className={selectClass}
            >
              {Object.keys(CURRICULUM_DATA).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Subject *</label>
            <select
              required
              value={subject}
              onChange={(e) => handleSubjectChange(e.target.value)}
              className={selectClass}
            >
              <option value="">Select subject</option>
              {subjects.map((s) => (
                <option key={s} value={s}>{SUBJECT_DISPLAY[s] ?? s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Grade *</label>
            <select
              required
              value={grade}
              onChange={(e) => setGrade(e.target.value)}
              className={selectClass}
              disabled={!subject}
            >
              <option value="">Select grade</option>
              {grades.map((g) => (
                <option key={g} value={g}>Grade {g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Page Ranges *</label>
            <input
              type="text"
              required
              value={pageRanges}
              onChange={(e) => setPageRanges(e.target.value)}
              className={inputClass}
              placeholder="e.g. 1-5, 10, 15-20"
            />
          </div>
          <div>
            <label className={labelClass}>Generation Type *</label>
            <select
              required
              value={generationType}
              onChange={(e) => setGenerationType(e.target.value)}
              className={selectClass}
            >
              {GENERATION_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeAnswerKey}
            onChange={(e) => setIncludeAnswerKey(e.target.checked)}
            className="accent-dars-terra w-4 h-4"
          />
          <span className="text-sm text-dars-ink">Include Answer Key</span>
        </label>

        <button
          type="submit"
          disabled={loading}
          className="px-5 py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? "Generating…" : "Generate"}
        </button>
      </form>
    </section>
  );
}

// ─── Generation Status / Result ───────────────────────────────────────────────

function GenerationResult({ initial }: { initial: ExamGeneration }) {
  const [eg, setEg] = useState<ExamGeneration>(initial);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef(Date.now());
  const MAX_POLL_MS = 120_000;

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  const fetchStatus = useCallback(async () => {
    const apiKey = getApiKey();
    try {
      const res = await fetch(`${API_URL}/api/v1/custom-exam-generations/${initial.id}`, {
        headers: { "X-API-Key": apiKey },
      });
      if (!res.ok) return;
      const data: ExamGeneration = await res.json();
      setEg(data);
      if (data.status === "READY" || data.status === "ERROR") {
        stopPolling();
      }
      if (Date.now() - startedAt.current > MAX_POLL_MS) {
        stopPolling();
      }
    } catch {
      // silent
    }
  }, [initial.id, stopPolling]);

  useEffect(() => {
    if (eg.status !== "READY" && eg.status !== "ERROR") {
      intervalRef.current = setInterval(fetchStatus, 3000);
    }
    return stopPolling;
  }, [fetchStatus, stopPolling, eg.status]);

  const statusColor =
    eg.status === "READY"
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : eg.status === "ERROR"
      ? "text-red-700 bg-red-50 border-red-200"
      : "text-dars-muted bg-dars-parchment border-dars-rule-light";

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="font-serif text-lg font-bold text-dars-ink">Latest Generation</h2>
        <span className={`text-xs font-semibold uppercase tracking-wide border rounded px-2 py-0.5 ${statusColor}`}>
          {eg.status}
        </span>
      </div>
      <p className="text-xs text-dars-muted mb-1">
        ID: <span className="font-mono">{eg.id}</span>
      </p>
      {eg.status !== "READY" && eg.status !== "ERROR" && (
        <p className="text-sm text-dars-muted mt-2 animate-pulse">Polling for result…</p>
      )}
      {eg.status === "ERROR" && (
        <p className="text-sm text-red-600 mt-2">Generation failed. Please try again.</p>
      )}
      {eg.status === "READY" && eg.result != null && (
        <div className="mt-4 border-t border-dars-rule-light pt-4">
          <p className="text-xs text-dars-muted mb-2 font-semibold uppercase tracking-wide">Result JSON</p>
          <div className="max-h-96 overflow-auto rounded-lg border border-dars-rule-light bg-dars-parchment p-4">
            <pre className="text-xs text-dars-ink whitespace-pre-wrap break-all">
              {JSON.stringify(eg.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
      {eg.status === "READY" && eg.result == null && (
        <p className="text-sm text-dars-muted mt-2">No result data returned.</p>
      )}
    </section>
  );
}

// ─── Past Exams ───────────────────────────────────────────────────────────────

const LIMIT = 10;

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "READY"
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : status === "ERROR"
      ? "text-red-700 bg-red-50 border-red-200"
      : "text-dars-muted bg-dars-parchment border-dars-rule-light";
  return (
    <span className={`text-[10px] font-semibold uppercase tracking-wide border rounded px-1.5 py-0.5 ${cls}`}>
      {status}
    </span>
  );
}

function PastExams({ refreshTrigger }: { refreshTrigger: number }) {
  const [items, setItems] = useState<ExamGeneration[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchPage = useCallback(async (off: number) => {
    setLoading(true);
    const apiKey = getApiKey();
    try {
      const res = await fetch(
        `${API_URL}/api/v1/custom-exam-generations?limit=${LIMIT}&offset=${off}`,
        { headers: { "X-API-Key": apiKey } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PaginatedResponse = await res.json();
      setItems(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load exam generations");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPage(offset);
  }, [offset, fetchPage, refreshTrigger]);

  function toggleExpand(id: string) {
    setExpandedId((prev) => (prev === id ? null : id));
  }

  const totalPages = Math.ceil(total / LIMIT);
  const currentPage = Math.floor(offset / LIMIT) + 1;

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-serif text-lg font-bold text-dars-ink">Past Exams</h2>
        {total > 0 && (
          <span className="text-xs text-dars-muted">
            {total} total · page {currentPage} of {totalPages}
          </span>
        )}
      </div>

      {loading && <p className="text-sm text-dars-muted animate-pulse">Loading…</p>}

      {!loading && items.length === 0 && (
        <p className="text-sm text-dars-muted">No exam generations yet.</p>
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-dars-rule-light">
          {items.map((eg) => (
            <li key={eg.id}>
              <button
                onClick={() => toggleExpand(eg.id)}
                className="w-full text-left py-3 px-1 hover:bg-dars-parchment transition-colors rounded cursor-pointer bg-transparent border-none"
              >
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="font-mono text-xs text-dars-muted shrink-0">
                    {eg.id.slice(0, 8)}…
                  </span>
                  <span className="text-sm text-dars-ink font-medium">
                    {eg.curriculum} · Grade {eg.grade} · {SUBJECT_DISPLAY[eg.subject] ?? eg.subject}
                  </span>
                  <StatusBadge status={eg.status} />
                  <span className="ml-auto text-xs text-dars-muted shrink-0">
                    {new Date(eg.created_at).toLocaleDateString()}
                  </span>
                </div>
              </button>
              {expandedId === eg.id && (
                <div className="px-1 pb-4">
                  {eg.status === "READY" && eg.result != null ? (
                    <div className="max-h-96 overflow-auto rounded-lg border border-dars-rule-light bg-dars-parchment p-4">
                      <pre className="text-xs text-dars-ink whitespace-pre-wrap break-all">
                        {JSON.stringify(eg.result, null, 2)}
                      </pre>
                    </div>
                  ) : eg.status === "READY" ? (
                    <p className="text-sm text-dars-muted">No result data.</p>
                  ) : (
                    <p className="text-sm text-dars-muted">
                      Result not available — status is {eg.status}.
                    </p>
                  )}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {totalPages > 1 && (
        <div className="flex items-center gap-2 mt-4 pt-4 border-t border-dars-rule-light">
          <button
            onClick={() => setOffset(Math.max(0, offset - LIMIT))}
            disabled={offset === 0 || loading}
            className="px-3 py-1.5 text-xs font-semibold text-dars-muted border border-dars-rule-dark rounded hover:text-dars-ink hover:bg-dars-parchment-deep transition-colors cursor-pointer bg-transparent disabled:opacity-40 disabled:cursor-not-allowed"
          >
            ← Prev
          </button>
          <span className="text-xs text-dars-muted flex-1 text-center">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={() => setOffset(offset + LIMIT)}
            disabled={offset + LIMIT >= total || loading}
            className="px-3 py-1.5 text-xs font-semibold text-dars-muted border border-dars-rule-dark rounded hover:text-dars-ink hover:bg-dars-parchment-deep transition-colors cursor-pointer bg-transparent disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Next →
          </button>
        </div>
      )}
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function PefExamGeneratorPage() {
  const [latestEg, setLatestEg] = useState<ExamGeneration | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  function handleGenerated(eg: ExamGeneration) {
    setLatestEg(eg);
    setTimeout(() => setRefreshTrigger((n) => n + 1), 1500);
  }

  return (
    <div className="p-8 max-w-4xl">
      <h1 className="font-serif text-2xl font-bold text-dars-ink mb-6">Exam Generator</h1>
      <GenerateForm onGenerated={handleGenerated} />
      {latestEg && <GenerationResult key={latestEg.id} initial={latestEg} />}
      <PastExams refreshTrigger={refreshTrigger} />
    </div>
  );
}
