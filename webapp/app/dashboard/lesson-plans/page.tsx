"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

interface LessonPlan {
  id: string;
  grade: string;
  subject: string;
  status: "PENDING" | "READY" | "ERROR" | string;
  created_at: string;
  content_html?: string | null;
}

interface PaginatedResponse {
  items: LessonPlan[];
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

// ─── Curriculum data (derived from LP Assistant config) ──────────────────────

const CURRICULUM_DATA: Record<string, Record<string, number[]>> = {
  ICT: {
    Eng:     [1, 2, 3, 4, 5],
    Maths:   [1, 2, 3, 4, 5],
    Urdu:    [1, 2, 3, 4, 5],
    Science: [4, 5],
  },
  Punjab: {
    Eng:   [1, 2, 3, 4, 5],
    Maths: [1, 2, 3, 4, 5],
    Urdu:  [1, 2, 3, 4, 5],
  },
  Sindh: {
    Eng:     [1, 2, 3, 4, 5],
    Maths:   [1, 2, 3, 4, 5],
    Urdu:    [1, 2, 3, 4, 5],
    Science: [5],
    GK:      [1, 2],
  },
};

// ─── Generate Form ────────────────────────────────────────────────────────────

function GenerateForm({ onGenerated }: { onGenerated: (lp: LessonPlan) => void }) {
  const [curriculum, setCurriculum] = useState("ICT");
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [pageNumber, setPageNumber] = useState("");
  const [topic, setTopic] = useState("");
  const [classStrength, setClassStrength] = useState("");
  const [generateBilingual, setGenerateBilingual] = useState(false);
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

    const body: Record<string, unknown> = {
      grade: Number(grade),
      subject,
      page_number: pageNumber,
      curriculum,
      generate_bilingual: generateBilingual,
    };
    if (topic.trim()) body.topic = topic.trim();
    if (classStrength.trim()) body.class_strength = Number(classStrength);

    try {
      const res = await fetch(`${API_URL}/api/v1/lesson-plans`, {
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
      const lp: LessonPlan = await res.json();
      onGenerated(lp);
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
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8 shadow-sm">
      <h2 className="font-serif text-lg font-bold text-dars-ink mb-4 flex items-center gap-2 before:content-[''] before:block before:w-1 before:h-5 before:bg-dars-terra before:rounded-full">Generate Lesson Plan</h2>
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Curriculum *</label>
            <select required value={curriculum} onChange={(e) => handleCurriculumChange(e.target.value)} className={selectClass}>
              {Object.keys(CURRICULUM_DATA).map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Subject *</label>
            <select required value={subject} onChange={(e) => handleSubjectChange(e.target.value)} className={selectClass}>
              <option value="">Select subject</option>
              {subjects.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Grade *</label>
            <select required value={grade} onChange={(e) => setGrade(e.target.value)} className={selectClass} disabled={!subject}>
              <option value="">Select grade</option>
              {grades.map((g) => (
                <option key={g} value={g}>Grade {g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className={labelClass}>Page Number *</label>
            <input
              type="text"
              required
              value={pageNumber}
              onChange={(e) => setPageNumber(e.target.value)}
              className={inputClass}
              placeholder="e.g. 42"
            />
          </div>
          <div>
            <label className={labelClass}>Topic</label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className={inputClass}
              placeholder="Optional"
            />
          </div>
          <div>
            <label className={labelClass}>Class Strength</label>
            <input
              type="number"
              min={1}
              value={classStrength}
              onChange={(e) => setClassStrength(e.target.value)}
              className={inputClass}
              placeholder="Optional"
            />
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={generateBilingual}
            onChange={(e) => setGenerateBilingual(e.target.checked)}
            className="accent-dars-terra w-4 h-4"
          />
          <span className="text-sm text-dars-ink">Generate Bilingual</span>
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

function GenerationResult({ initial }: { initial: LessonPlan }) {
  const [lp, setLp] = useState<LessonPlan>(initial);
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
      const res = await fetch(`${API_URL}/api/v1/lesson-plans/${initial.id}`, {
        headers: { "X-API-Key": apiKey },
      });
      if (!res.ok) return;
      const data: LessonPlan = await res.json();
      setLp(data);
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
    if (lp.status !== "READY" && lp.status !== "ERROR") {
      intervalRef.current = setInterval(fetchStatus, 3000);
    }
    return stopPolling;
  }, [fetchStatus, stopPolling, lp.status]);

  const statusColor =
    lp.status === "READY"
      ? "text-emerald-700 bg-emerald-50 border-emerald-200"
      : lp.status === "ERROR"
      ? "text-red-700 bg-red-50 border-red-200"
      : "text-dars-muted bg-dars-parchment border-dars-rule-light";

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8 shadow-sm">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="font-serif text-lg font-bold text-dars-ink">Latest Generation</h2>
        <span
          className={`text-xs font-semibold uppercase tracking-wide border rounded px-2 py-0.5 ${statusColor}`}
        >
          {lp.status}
        </span>
      </div>
      <p className="text-xs text-dars-muted mb-1">
        ID: <span className="font-mono">{lp.id}</span>
      </p>
      {lp.status !== "READY" && lp.status !== "ERROR" && (
        <p className="text-sm text-dars-muted mt-2 animate-pulse">Polling for result…</p>
      )}
      {lp.status === "ERROR" && (
        <p className="text-sm text-red-600 mt-2">Generation failed. Please try again.</p>
      )}
      {lp.status === "READY" && lp.content_html && (
        <div
          className="mt-4 prose prose-sm max-w-none border-t border-dars-rule-light pt-4"
          dangerouslySetInnerHTML={{ __html: lp.content_html }}
        />
      )}
      {lp.status === "READY" && !lp.content_html && (
        <p className="text-sm text-dars-muted mt-2">No HTML content returned.</p>
      )}
    </section>
  );
}

// ─── Past Lesson Plans ────────────────────────────────────────────────────────

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

function PastLessonPlans({ refreshTrigger }: { refreshTrigger: number }) {
  const [items, setItems] = useState<LessonPlan[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchPage = useCallback(async (off: number) => {
    setLoading(true);
    const apiKey = getApiKey();
    try {
      const res = await fetch(
        `${API_URL}/api/v1/lesson-plans?limit=${LIMIT}&offset=${off}`,
        { headers: { "X-API-Key": apiKey } }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: PaginatedResponse = await res.json();
      setItems(data.items);
      setTotal(data.total);
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Failed to load lesson plans");
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
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="font-serif text-lg font-bold text-dars-ink flex items-center gap-2 before:content-[''] before:block before:w-1 before:h-5 before:bg-dars-terra before:rounded-full">Past Lesson Plans</h2>
        {total > 0 && (
          <span className="text-xs text-dars-muted">
            {total} total · page {currentPage} of {totalPages}
          </span>
        )}
      </div>

      {loading && <p className="text-sm text-dars-muted animate-pulse">Loading…</p>}

      {!loading && items.length === 0 && (
        <p className="text-sm text-dars-muted">No lesson plans yet.</p>
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-dars-rule-light">
          {items.map((lp) => (
            <li key={lp.id}>
              <button
                onClick={() => toggleExpand(lp.id)}
                className="w-full text-left py-3 px-1 hover:bg-dars-parchment transition-colors rounded cursor-pointer bg-transparent border-none"
              >
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="font-mono text-xs text-dars-muted shrink-0">
                    {lp.id.slice(0, 8)}…
                  </span>
                  <span className="text-sm text-dars-ink font-medium">
                    {lp.grade} · {lp.subject}
                  </span>
                  <StatusBadge status={lp.status} />
                  <span className="ml-auto text-xs text-dars-muted shrink-0">
                    {new Date(lp.created_at).toLocaleDateString()}
                  </span>
                </div>
              </button>
              {expandedId === lp.id && (
                <div className="px-1 pb-4">
                  {lp.status === "READY" && lp.content_html ? (
                    <div
                      className="prose prose-sm max-w-none border border-dars-rule-light rounded-lg p-4 bg-dars-parchment"
                      dangerouslySetInnerHTML={{ __html: lp.content_html }}
                    />
                  ) : lp.status === "READY" ? (
                    <p className="text-sm text-dars-muted">No HTML content.</p>
                  ) : (
                    <p className="text-sm text-dars-muted">
                      Content not available — status is {lp.status}.
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

export default function LessonPlansPage() {
  const [latestLp, setLatestLp] = useState<LessonPlan | null>(null);
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  function handleGenerated(lp: LessonPlan) {
    setLatestLp(lp);
    setTimeout(() => setRefreshTrigger((n) => n + 1), 1500);
  }

  return (
    <div className="px-8 py-8 max-w-4xl">
      <div className="mb-8 pb-6 border-b border-dars-rule-light">
        <h1 className="font-serif text-2xl font-bold text-dars-ink">Lesson Plans</h1>
        <p className="text-sm text-dars-muted mt-1">Generate and manage curriculum-aligned lesson plans.</p>
      </div>
      <GenerateForm onGenerated={handleGenerated} />
      {latestLp && <GenerationResult key={latestLp.id} initial={latestLp} />}
      <PastLessonPlans refreshTrigger={refreshTrigger} />
    </div>
  );
}
