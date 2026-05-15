"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { use } from "react";
import Link from "next/link";
import {
  getChapterPlansByCst,
  getLessonSlotsByChapter,
  getAssessmentSlotsByCst,
  markTaught,
  generateLPForSlot,
  generateAllLPs,
  generateExamForSlot,
  getCst,
  getTimetable,
  type ChapterPlanWithDates,
  type ClassLessonSlotRead,
  type AssessmentSlotRead,
} from "@/lib/school-api";
import { getMockLP, getMockExam } from "@/lib/teacher-app-mocks";
import { ExamPaperView } from "../../_components/exam-paper-view";

// ---------------------------------------------------------------------------
// LP slide-over
// ---------------------------------------------------------------------------

function LPSlideOver({ lpId, subject, onClose }: { lpId: string; subject: string; onClose: () => void }) {
  const lp = getMockLP(lpId, subject);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white h-full shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900 text-sm">Lesson Plan</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 bg-transparent border-none cursor-pointer p-1">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          {lp.content && (
            <div className="prose prose-sm max-w-none" dangerouslySetInnerHTML={{ __html: lp.content }} />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Exam slide-over
// ---------------------------------------------------------------------------

function ExamSlideOver({ examId, subject, onClose }: { examId: string; subject: string; onClose: () => void }) {
  const exam = getMockExam(examId, subject);

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/30" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white h-full shadow-xl flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-200">
          <h2 className="font-semibold text-gray-900 text-sm">Exam</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 bg-transparent border-none cursor-pointer p-1">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto p-5">
          <ExamPaperView result={exam.result} />
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Lessons tab
// ---------------------------------------------------------------------------

function LPTypeBadge({ type }: { type: string }) {
  const colors: Record<string, string> = {
    Reading: "bg-blue-100 text-blue-800",
    Grammar: "bg-indigo-100 text-indigo-800",
    Concept: "bg-orange-100 text-orange-800",
    Practice: "bg-yellow-100 text-yellow-800",
    Revision: "bg-amber-100 text-amber-800",
    Introduction: "bg-blue-100 text-blue-800",
  };
  const cls = colors[type] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded ${cls}`}>{type}</span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "taught"
      ? "bg-green-100 text-green-700"
      : status === "planned"
      ? "bg-gray-100 text-gray-600"
      : "bg-amber-100 text-amber-700";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded ${cls} capitalize`}>{status}</span>
  );
}

function LessonsTab({ cstId, subject }: { cstId: string; subject: string }) {
  const [chapters, setChapters] = useState<ChapterPlanWithDates[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<ChapterPlanWithDates | null>(null);
  const [slots, setSlots] = useState<ClassLessonSlotRead[]>([]);
  const [loadingChapters, setLoadingChapters] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [generatingAll, setGeneratingAll] = useState(false);
  const [generatingSlot, setGeneratingSlot] = useState<string | null>(null);
  const [viewLpId, setViewLpId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getChapterPlansByCst(cstId)
      .then((data) => setChapters(data.items))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load chapters"))
      .finally(() => setLoadingChapters(false));
  }, [cstId]);

  const loadSlots = useCallback(async (plan: ChapterPlanWithDates) => {
    setLoadingSlots(true);
    try {
      const data = await getLessonSlotsByChapter(plan.id);
      setSlots(data.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to load slots");
    } finally {
      setLoadingSlots(false);
    }
  }, []);

  // Poll for pending LPs every 3s
  useEffect(() => {
    const hasPending = slots.some((s) => {
      // We can't poll by lesson_plan_id status here without fetching each LP,
      // but we can re-fetch slots to detect when lesson_plan_id changes
      return false; // LP status is not in slot; just re-fetch slots on interval if any slot has no LP
    });
    if (!hasPending) {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
      return;
    }
  }, [slots]);

  // Simplified polling: if generating, re-fetch slots every 3s
  useEffect(() => {
    if (generatingAll || generatingSlot) {
      pollRef.current = setInterval(async () => {
        if (selectedChapter) {
          const data = await getLessonSlotsByChapter(selectedChapter.id);
          setSlots(data.items);
          // Stop polling once all slots have lesson_plan_id
          const allLinked = data.items.every((s) => s.lesson_plan_id !== null);
          if (allLinked) {
            if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
            setGeneratingAll(false);
            setGeneratingSlot(null);
          }
        }
      }, 3000);
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    };
  }, [generatingAll, generatingSlot, selectedChapter]);

  async function handleSelectChapter(plan: ChapterPlanWithDates) {
    setSelectedChapter(plan);
    setSlots([]);
    await loadSlots(plan);
  }

  async function handleGenerateLP(slot: ClassLessonSlotRead) {
    setGeneratingSlot(slot.id);
    try {
      await generateLPForSlot(slot.id);
    } catch { /* 409 = already has LP */ }
  }

  async function handleGenerateAll() {
    if (!selectedChapter) return;
    setGeneratingAll(true);
    try {
      await generateAllLPs(selectedChapter.id);
    } catch { /* silent */ }
  }

  async function handleMarkTaught(slot: ClassLessonSlotRead) {
    try {
      await markTaught(slot.id);
      if (selectedChapter) await loadSlots(selectedChapter);
    } catch { /* silent */ }
  }

  if (loadingChapters) {
    return <p className="text-sm text-gray-400 animate-pulse py-4">Loading chapters…</p>;
  }

  if (chapters.length === 0) {
    return (
      <div className="text-center py-8 text-sm text-gray-400">
        No chapter plans. Set them up in the{" "}
        <Link href="/dashboard/curriculum-demo" className="text-amber-600 underline">dashboard</Link>.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>}

      {/* Chapter selector */}
      <div>
        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Select Chapter
        </label>
        <select
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
          value={selectedChapter?.id ?? ""}
          onChange={(e) => {
            const plan = chapters.find((c) => c.id === e.target.value);
            if (plan) handleSelectChapter(plan);
          }}
        >
          <option value="">Choose a chapter…</option>
          {chapters.map((c) => (
            <option key={c.id} value={c.id}>
              Position {c.position} — {c.teaching_days} days
            </option>
          ))}
        </select>
      </div>

      {selectedChapter && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs text-gray-400">
              {slots.length} slots · {slots.filter((s) => s.status === "taught").length} taught
            </p>
            <button
              onClick={handleGenerateAll}
              disabled={generatingAll}
              className="text-xs px-3 py-1.5 bg-amber-600 text-white rounded-md hover:bg-amber-700 transition-colors border-none cursor-pointer font-medium disabled:opacity-50"
            >
              {generatingAll ? "Generating…" : "Generate All LPs"}
            </button>
          </div>

          {loadingSlots ? (
            <p className="text-sm text-gray-400 animate-pulse">Loading slots…</p>
          ) : slots.length === 0 ? (
            <p className="text-sm text-gray-400">No lesson slots for this chapter.</p>
          ) : (
            <div className="space-y-2">
              {slots.map((slot) => (
                <div
                  key={slot.id}
                  className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg"
                >
                  <div className="w-6 h-6 shrink-0 rounded-full bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-500">
                    {slot.day_number}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-gray-900 truncate font-medium">{slot.title}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <LPTypeBadge type={slot.lp_type} />
                      <StatusBadge status={slot.status} />
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {slot.lesson_plan_id ? (
                      <button
                        onClick={() => setViewLpId(slot.lesson_plan_id)}
                        className="text-xs px-2.5 py-1 border border-amber-300 text-amber-700 rounded hover:bg-amber-50 transition-colors bg-transparent cursor-pointer"
                      >
                        View LP
                      </button>
                    ) : (
                      <button
                        onClick={() => handleGenerateLP(slot)}
                        disabled={generatingSlot === slot.id}
                        className="text-xs px-2.5 py-1 border border-gray-200 text-gray-600 rounded hover:bg-gray-50 transition-colors bg-transparent cursor-pointer disabled:opacity-50"
                      >
                        {generatingSlot === slot.id ? "…" : "Generate LP"}
                      </button>
                    )}
                    {slot.status === "planned" && (
                      <button
                        onClick={() => handleMarkTaught(slot)}
                        className="text-xs px-2.5 py-1 bg-green-600 text-white rounded hover:bg-green-700 transition-colors border-none cursor-pointer"
                      >
                        Taught
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {viewLpId && <LPSlideOver lpId={viewLpId} subject={subject} onClose={() => setViewLpId(null)} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assessments tab
// ---------------------------------------------------------------------------

function AssessmentsTab({ cstId, subject }: { cstId: string; subject: string }) {
  const [slots, setSlots] = useState<AssessmentSlotRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [generatingSlot, setGeneratingSlot] = useState<string | null>(null);
  const [viewExamId, setViewExamId] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getAssessmentSlotsByCst(cstId)
      .then((data) => setSlots(data.items))
      .finally(() => setLoading(false));
  }, [cstId]);

  // Poll while generating
  useEffect(() => {
    if (generatingSlot) {
      pollRef.current = setInterval(async () => {
        const data = await getAssessmentSlotsByCst(cstId);
        setSlots(data.items);
        const slot = data.items.find((s) => s.id === generatingSlot);
        if (slot?.exam_id) {
          setGeneratingSlot(null);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      }, 3000);
    }
    return () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  }, [generatingSlot, cstId]);

  async function handleGenerateExam(slot: AssessmentSlotRead) {
    setGeneratingSlot(slot.id);
    try {
      await generateExamForSlot(slot.id);
    } catch { /* 409 = already generated */ }
  }

  if (loading) return <p className="text-sm text-gray-400 animate-pulse py-4">Loading assessments…</p>;
  if (slots.length === 0) return <p className="text-sm text-gray-400 py-4">No assessment slots scheduled.</p>;

  return (
    <div className="space-y-2">
      {slots.map((slot) => (
        <div key={slot.id} className="flex items-center gap-3 p-3 bg-white border border-gray-200 rounded-lg">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span
                className={`text-xs font-semibold px-2 py-0.5 rounded uppercase ${
                  slot.assessment_type === "formative"
                    ? "bg-rose-100 text-rose-700"
                    : "bg-violet-100 text-violet-700"
                }`}
              >
                {slot.assessment_type === "formative" ? "FA" : "SA"}
              </span>
              <StatusBadge status={slot.status} />
            </div>
            {slot.title && <p className="text-sm font-medium text-gray-900">{slot.title}</p>}
            <p className="text-xs text-gray-400 mt-0.5">{slot.scheduled_date}</p>
          </div>
          <div className="shrink-0">
            {slot.exam_id ? (
              <button
                onClick={() => setViewExamId(slot.exam_id)}
                className="text-xs px-2.5 py-1 border border-violet-300 text-violet-700 rounded hover:bg-violet-50 transition-colors bg-transparent cursor-pointer"
              >
                View Exam
              </button>
            ) : (
              <button
                onClick={() => handleGenerateExam(slot)}
                disabled={generatingSlot === slot.id}
                className="text-xs px-2.5 py-1 border border-gray-200 text-gray-600 rounded hover:bg-gray-50 transition-colors bg-transparent cursor-pointer disabled:opacity-50"
              >
                {generatingSlot === slot.id ? "…" : "Generate Exam"}
              </button>
            )}
          </div>
        </div>
      ))}

      {viewExamId && <ExamSlideOver examId={viewExamId} subject={subject} onClose={() => setViewExamId(null)} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Timetable tab
// ---------------------------------------------------------------------------

const DAYS = [
  { label: "Mon", value: 0 },
  { label: "Tue", value: 1 },
  { label: "Wed", value: 2 },
  { label: "Thu", value: 3 },
  { label: "Fri", value: 4 },
  { label: "Sat", value: 5 },
];

function TimetableTab({ cstId }: { cstId: string }) {
  const [days, setDays] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const cst = await getCst(cstId);
        const tt = await getTimetable(String(cst.class_id), cstId);
        setDays(tt.items.map((s) => s.day_of_week).sort((a, b) => a - b));
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : "Failed to load timetable");
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [cstId]);

  if (loading) return <p className="text-sm text-gray-400 animate-pulse py-4">Loading timetable…</p>;

  return (
    <div className="space-y-4">
      {error && (
        <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
      )}
      <div>
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Class days</p>
        <div className="flex gap-2 flex-wrap">
          {DAYS.map((d) => (
            <span
              key={d.value}
              className={`px-5 py-2.5 rounded-lg text-sm font-semibold border ${
                days.includes(d.value)
                  ? "bg-amber-600 text-white border-amber-600"
                  : "bg-gray-50 text-gray-300 border-gray-200"
              }`}
            >
              {d.label}
            </span>
          ))}
        </div>
        <p className="text-xs text-gray-400 mt-3">
          Class days are set automatically based on your academic year schedule.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ClassDetailPage({
  params,
}: {
  params: Promise<{ cst_id: string }>;
}) {
  const { cst_id } = use(params);
  const [tab, setTab] = useState<"lessons" | "assessments" | "timetable">("lessons");
  const [subject, setSubject] = useState<string>("");

  useEffect(() => {
    getCst(cst_id)
      .then((cst) => setSubject(cst.subject ?? ""))
      .catch(() => setSubject(""));
  }, [cst_id]);

  const TAB_LABELS: Record<"lessons" | "assessments" | "timetable", string> = {
    lessons: "Lessons",
    assessments: "Assessments",
    timetable: "Timetable",
  };

  return (
    <div>
      <div className="mb-6 flex items-center gap-3">
        <Link href="/teacher-app/classes" className="text-gray-400 hover:text-gray-600 transition-colors no-underline">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
          </svg>
        </Link>
        <h1 className="text-xl font-semibold text-gray-900">Class Detail</h1>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-gray-200">
        {(["lessons", "assessments", "timetable"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors bg-transparent cursor-pointer ${
              tab === t
                ? "border-amber-600 text-amber-700"
                : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300"
            }`}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {tab === "lessons" && <LessonsTab cstId={cst_id} subject={subject} />}
      {tab === "assessments" && <AssessmentsTab cstId={cst_id} subject={subject} />}
      {tab === "timetable" && <TimetableTab cstId={cst_id} />}
    </div>
  );
}
