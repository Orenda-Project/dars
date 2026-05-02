"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { toast } from "sonner";
import Link from "next/link";

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

function getApiKey(): string {
  if (typeof window === "undefined") return "";
  const raw = localStorage.getItem("dars_pef_session");
  if (!raw) return "";
  try { return JSON.parse(raw).api_key ?? ""; } catch { return ""; }
}

// ─── Static option data (mirrors UG_EG config.py) ────────────────────────────

const CURRICULUM_SUBJECTS: Record<string, Record<string, number[]>> = {
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
  Eng: "English", Maths: "Mathematics", Urdu: "Urdu",
  Islamiat: "Islamiat", GenSci: "Science", GenK: "General Knowledge", SST: "Social Studies",
};

const GENERATION_TYPES = [
  { value: "exam", label: "Exam" },
  { value: "class_assessment", label: "Class Assessment" },
];

const ENG_URDU_OBJECTIVE = [
  "MCQs", "MSQs", "Fill in the Blanks", "Missing Letters", "True/False",
  "Match Columns", "Circle the Correct", "Rewrite Sentences", "Brief Answers",
  "Listening", "Speaking", "Reading",
];
const ENG_URDU_SUBJECTIVE = [
  "Word Meanings", "Word Sentences", "Comprehension", "Rewriting", "Story Completion",
  "Simple Writing", "Formal Letter", "Informal Letter", "Application Writing",
  "Story Writing", "Essay Writing", "Paragraph Writing", "Picture Description",
  "Project Work", "Brief Answers", "Mind Map", "Label the Diagram", "Flow Chart",
  "Logical Reasoning",
];
const MATHS_OBJECTIVE = [
  "MCQs", "MSQs", "Fill in the Blanks", "True/False", "Match Columns",
  "Mental Math", "Missing Gaps", "Sequences",
];
const MATHS_SUBJECTIVE = ["Short Questions", "Restricted Questions", "Long Question"];
const LONG_QUESTION_SUB_TYPES = ["Word Problems", "Graphs & Geometric Problems"];

function getObjectiveTypes(subject: string) {
  return subject === "Maths" ? MATHS_OBJECTIVE : ENG_URDU_OBJECTIVE;
}
function getSubjectiveTypes(subject: string) {
  return subject === "Maths" ? MATHS_SUBJECTIVE : ENG_URDU_SUBJECTIVE;
}

// ─── No-curriculum banner ─────────────────────────────────────────────────────

function NoCurriculumBanner() {
  return (
    <div className="mb-6 flex items-start gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
      <span className="mt-0.5 text-amber-500 shrink-0">⚠</span>
      <span>
        Your account has no curriculum configured. Exam generation requires a curriculum.{" "}
        <Link href="/dashboard/settings" className="font-semibold underline underline-offset-2 hover:text-amber-900">
          Go to Settings to select ICT or Punjab.
        </Link>
      </span>
    </div>
  );
}

// ─── Checkbox list helper ─────────────────────────────────────────────────────

function CheckboxList({ label, options, selected, onChange }: {
  label: string; options: string[]; selected: string[]; onChange: (v: string[]) => void;
}) {
  function toggle(val: string) {
    onChange(selected.includes(val) ? selected.filter((x) => x !== val) : [...selected, val]);
  }
  return (
    <div>
      <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-2">{label}</p>
      <div className="flex flex-wrap gap-x-4 gap-y-1.5">
        {options.map((o) => (
          <label key={o} className="flex items-center gap-1.5 text-sm text-dars-ink cursor-pointer select-none">
            <input type="checkbox" checked={selected.includes(o)} onChange={() => toggle(o)} className="accent-dars-terra w-3.5 h-3.5" />
            {o}
          </label>
        ))}
      </div>
    </div>
  );
}

// ─── Count input per question type ───────────────────────────────────────────

function CountInputs({ label, types, counts, onChange }: {
  label: string; types: string[]; counts: Record<string, number>; onChange: (v: Record<string, number>) => void;
}) {
  if (types.length === 0) return null;
  return (
    <div>
      <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-2">{label}</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
        {types.map((t) => (
          <div key={t} className="flex items-center gap-2">
            <span className="text-xs text-dars-ink flex-1 truncate">{t}</span>
            <input
              type="number" min={0} max={20}
              value={counts[t] ?? 0}
              onChange={(e) => onChange({ ...counts, [t]: parseInt(e.target.value) || 0 })}
              className="w-14 border border-dars-rule-dark rounded px-2 py-1 text-xs text-dars-ink focus:outline-none focus:ring-1 focus:ring-dars-terra"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Generate Form ────────────────────────────────────────────────────────────

function GenerateForm({ curriculum, onGenerated }: {
  curriculum: string; onGenerated: (eg: ExamGeneration) => void;
}) {
  const subjects = Object.keys(CURRICULUM_SUBJECTS[curriculum] ?? {});
  const [subject, setSubject] = useState("");
  const [grade, setGrade] = useState("");
  const [pageRanges, setPageRanges] = useState("");
  const [generationType, setGenerationType] = useState("exam");
  const [questionTypes, setQuestionTypes] = useState<string[]>(["seen", "unseen"]);
  const [seenCategories, setSeenCategories] = useState<string[]>(["objective", "subjective"]);
  const [unseenCategories, setUnseenCategories] = useState<string[]>(["objective", "subjective"]);
  const [unseenObjTypes, setUnseenObjTypes] = useState<string[]>([]);
  const [unseenSubjTypes, setUnseenSubjTypes] = useState<string[]>([]);
  const [unseenObjCounts, setUnseenObjCounts] = useState<Record<string, number>>({});
  const [unseenSubjCounts, setUnseenSubjCounts] = useState<Record<string, number>>({});
  const [longQuestionSubTypes, setLongQuestionSubTypes] = useState<string[]>([]);
  const [includeAnswerKey, setIncludeAnswerKey] = useState(false);
  const [imageGenEnabled, setImageGenEnabled] = useState(false);
  const [enableReview, setEnableReview] = useState(false);
  const [loading, setLoading] = useState(false);

  const grades = subject ? (CURRICULUM_SUBJECTS[curriculum]?.[subject] ?? []) : [];
  const objTypes = getObjectiveTypes(subject);
  const subjTypes = getSubjectiveTypes(subject);
  const hasUnseen = questionTypes.includes("unseen");
  const unseenHasObj = hasUnseen && unseenCategories.includes("objective");
  const unseenHasSubj = hasUnseen && unseenCategories.includes("subjective");
  const showLongSubTypes = subject === "Maths" && unseenSubjTypes.includes("Long Question");

  function handleSubjectChange(val: string) {
    setSubject(val); setGrade("");
    setUnseenObjTypes([]); setUnseenSubjTypes([]);
    setUnseenObjCounts({}); setUnseenSubjCounts({});
    setLongQuestionSubTypes([]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (questionTypes.length === 0) { toast.error("Select at least one question type (seen/unseen)"); return; }
    setLoading(true);

    const body: Record<string, unknown> = {
      subject, grade: Number(grade), page_ranges: pageRanges,
      generation_type: generationType, question_types: questionTypes,
      include_answer_key: includeAnswerKey,
      image_generation_enabled: imageGenEnabled,
      enable_review: enableReview,
    };
    if (questionTypes.includes("seen") && seenCategories.length > 0)
      body.seen_categories = seenCategories;
    if (hasUnseen) {
      body.unseen_categories = unseenCategories;
      if (unseenHasObj && unseenObjTypes.length > 0) {
        body.unseen_objective_types = unseenObjTypes;
        const fc = Object.fromEntries(Object.entries(unseenObjCounts).filter(([k]) => unseenObjTypes.includes(k) && unseenObjCounts[k] > 0));
        if (Object.keys(fc).length > 0) body.unseen_objective_counts = fc;
      }
      if (unseenHasSubj && unseenSubjTypes.length > 0) {
        body.unseen_subjective_types = unseenSubjTypes;
        const fc = Object.fromEntries(Object.entries(unseenSubjCounts).filter(([k]) => unseenSubjTypes.includes(k) && unseenSubjCounts[k] > 0));
        if (Object.keys(fc).length > 0) body.unseen_subjective_counts = fc;
      }
      if (showLongSubTypes && longQuestionSubTypes.length > 0)
        body.long_question_sub_types = longQuestionSubTypes;
    }

    try {
      const res = await fetch(`${API_URL}/api/v1/custom-exam-generations`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-API-Key": getApiKey() },
        body: JSON.stringify(body),
      });
      if (!res.ok) { const t = await res.text(); throw new Error(t || `HTTP ${res.status}`); }
      onGenerated(await res.json());
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  const selectCls = "w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra";
  const labelCls = "block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide";
  const sectionCls = "border border-dars-rule-light rounded-lg p-4 space-y-4";

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      <div className={sectionCls}>
        <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide">Exam Details</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>Subject *</label>
            <select required value={subject} onChange={(e) => handleSubjectChange(e.target.value)} className={selectCls}>
              <option value="">Select subject</option>
              {subjects.map((s) => <option key={s} value={s}>{SUBJECT_DISPLAY[s] ?? s}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>Grade *</label>
            <select required value={grade} onChange={(e) => setGrade(e.target.value)} className={selectCls} disabled={!subject}>
              <option value="">Select grade</option>
              {grades.map((g) => <option key={g} value={g}>Grade {g}</option>)}
            </select>
          </div>
          <div>
            <label className={labelCls}>Page Ranges *</label>
            <input type="text" required value={pageRanges} onChange={(e) => setPageRanges(e.target.value)} className={selectCls} placeholder="e.g. 1-5, 10, 15-20" />
          </div>
          <div>
            <label className={labelCls}>Generation Type *</label>
            <select required value={generationType} onChange={(e) => setGenerationType(e.target.value)} className={selectCls}>
              {GENERATION_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      <div className={sectionCls}>
        <CheckboxList label="Question Sources *" options={["seen", "unseen"]} selected={questionTypes} onChange={setQuestionTypes} />
        {questionTypes.includes("seen") && (
          <CheckboxList label="Seen — Categories" options={["objective", "subjective"]} selected={seenCategories} onChange={setSeenCategories} />
        )}
        {hasUnseen && (
          <>
            <CheckboxList label="Unseen — Categories" options={["objective", "subjective"]} selected={unseenCategories} onChange={setUnseenCategories} />
            {unseenHasObj && subject && (
              <>
                <CheckboxList label="Unseen Objective — Types" options={objTypes} selected={unseenObjTypes} onChange={setUnseenObjTypes} />
                <CountInputs label="Unseen Objective — Counts" types={unseenObjTypes} counts={unseenObjCounts} onChange={setUnseenObjCounts} />
              </>
            )}
            {unseenHasSubj && subject && (
              <>
                <CheckboxList label="Unseen Subjective — Types" options={subjTypes} selected={unseenSubjTypes} onChange={setUnseenSubjTypes} />
                <CountInputs label="Unseen Subjective — Counts" types={unseenSubjTypes} counts={unseenSubjCounts} onChange={setUnseenSubjCounts} />
                {showLongSubTypes && (
                  <CheckboxList label="Long Question — Sub-types" options={LONG_QUESTION_SUB_TYPES} selected={longQuestionSubTypes} onChange={setLongQuestionSubTypes} />
                )}
              </>
            )}
          </>
        )}
      </div>

      <div className={sectionCls}>
        <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide">Options</p>
        <div className="flex flex-wrap gap-6">
          {([
            ["Include Answer Key", includeAnswerKey, setIncludeAnswerKey],
            ["Image Generation", imageGenEnabled, setImageGenEnabled],
            ["AI Review", enableReview, setEnableReview],
          ] as [string, boolean, (v: boolean) => void][]).map(([label, val, set]) => (
            <label key={label} className="flex items-center gap-2 cursor-pointer select-none">
              <input type="checkbox" checked={val} onChange={(e) => set(e.target.checked)} className="accent-dars-terra w-4 h-4" />
              <span className="text-sm text-dars-ink">{label}</span>
            </label>
          ))}
        </div>
      </div>

      <button type="submit" disabled={loading}
        className="px-5 py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-50 disabled:cursor-not-allowed">
        {loading ? "Generating…" : "Generate"}
      </button>
    </form>
  );
}

// ─── Result + polling ─────────────────────────────────────────────────────────

function GenerationResult({ initial }: { initial: ExamGeneration }) {
  const [eg, setEg] = useState<ExamGeneration>(initial);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef(Date.now());

  const stopPolling = useCallback(() => {
    if (intervalRef.current) { clearInterval(intervalRef.current); intervalRef.current = null; }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/v1/custom-exam-generations/${initial.id}`, { headers: { "X-API-Key": getApiKey() } });
      if (!res.ok) return;
      const data: ExamGeneration = await res.json();
      setEg(data);
      if (data.status === "READY" || data.status === "ERROR") stopPolling();
      if (Date.now() - startedAt.current > 120_000) stopPolling();
    } catch { /* silent */ }
  }, [initial.id, stopPolling]);

  useEffect(() => {
    if (eg.status !== "READY" && eg.status !== "ERROR") intervalRef.current = setInterval(fetchStatus, 3000);
    return stopPolling;
  }, [fetchStatus, stopPolling, eg.status]);

  const statusCls = eg.status === "READY" ? "text-emerald-700 bg-emerald-50 border-emerald-200"
    : eg.status === "ERROR" ? "text-red-700 bg-red-50 border-red-200"
    : "text-dars-muted bg-dars-parchment border-dars-rule-light";

  return (
    <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8">
      <div className="flex items-center gap-3 mb-4">
        <h2 className="font-serif text-lg font-bold text-dars-ink">Latest Generation</h2>
        <span className={`text-xs font-semibold uppercase tracking-wide border rounded px-2 py-0.5 ${statusCls}`}>{eg.status}</span>
      </div>
      <p className="text-xs text-dars-muted mb-1">ID: <span className="font-mono">{eg.id}</span></p>
      {eg.status !== "READY" && eg.status !== "ERROR" && <p className="text-sm text-dars-muted mt-2 animate-pulse">Polling for result…</p>}
      {eg.status === "ERROR" && <p className="text-sm text-red-600 mt-2">Generation failed. Please try again.</p>}
      {eg.status === "READY" && eg.result != null && (
        <div className="mt-4 border-t border-dars-rule-light pt-4">
          <p className="text-xs text-dars-muted mb-2 font-semibold uppercase tracking-wide">Result JSON</p>
          <div className="max-h-96 overflow-auto rounded-lg border border-dars-rule-light bg-dars-parchment p-4">
            <pre className="text-xs text-dars-ink whitespace-pre-wrap break-all">{JSON.stringify(eg.result, null, 2)}</pre>
          </div>
        </div>
      )}
      {eg.status === "READY" && eg.result == null && <p className="text-sm text-dars-muted mt-2">No result data returned.</p>}
    </section>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function ExamGeneratorPage() {
  const [curriculum, setCurriculum] = useState<string | null>(null);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [latestEg, setLatestEg] = useState<ExamGeneration | null>(null);

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
        <h1 className="font-serif text-2xl font-bold text-dars-ink">Exam Generator</h1>
        <p className="text-sm text-dars-muted mt-1">Generate curriculum-aligned exams and class assessments.</p>
      </div>
      {!loadingProfile && !curriculum && <NoCurriculumBanner />}
      <section className="bg-white border border-dars-rule-light rounded-xl p-6 mb-8 shadow-sm">
        <h2 className="font-serif text-lg font-bold text-dars-ink mb-5 flex items-center gap-2 before:content-[''] before:block before:w-1 before:h-5 before:bg-dars-terra before:rounded-full">Generate Exam</h2>
        {curriculum ? (
          <GenerateForm curriculum={curriculum} onGenerated={setLatestEg} />
        ) : (
          <p className="text-sm text-dars-muted">Set your curriculum in Settings to generate exams.</p>
        )}
      </section>
      {latestEg && <GenerationResult key={latestEg.id} initial={latestEg} />}
    </div>
  );
}
