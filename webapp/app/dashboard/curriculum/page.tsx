"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { BookLoader } from "@/components/atoms/book-loader";
import { getApiKey, isAdmin } from "@/lib/session";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Book {
  id: string;
  curriculum: string;
  grade: string;
  subject: string;
  title: string;
  publisher: string;
  total_chapters: number;
}

interface Chapter {
  id: string;
  book_id: string;
  title: string;
  chapter_number: number;
  start_page: number | null;
  end_page: number | null;
}

interface Topic {
  id: string;
  chapter_id: string;
  topic_number: number;
  title: string;
  start_page: number | null;
  end_page: number | null;
}

interface Slot {
  id: string;
  topic_id: string;
  day_number: number;
  scheduled_date: string | null;
  topic_subtopic: string;
  lesson_plan_id: string | null;
}

interface LessonPlan {
  id: string;
  topic: string | null;
  grade: string;
  subject: string;
  curriculum: string;
  status: string;
  content: string | null;
  content_bilingual: string | null;
}

interface Assessment {
  id: string;
  lesson_plan_id: string;
  status: string;
  content: string | null;
  content_json: object[] | null;
}

// ── Spinner ───────────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

// ── LP Panel (slide-over) ─────────────────────────────────────────────────────

function LPPanel({ lpId, onClose }: { lpId: string; onClose: () => void }) {
  const [lp, setLp] = useState<LessonPlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [bilingual, setBilingual] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/v1/lesson-plans/${lpId}`, {
      headers: { "X-API-Key": getApiKey() },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: LessonPlan) => setLp(data))
      .catch(() => { toast.error("Failed to load lesson plan"); })
      .finally(() => setLoading(false));
  }, [lpId]);

  const html = bilingual ? lp?.content_bilingual : lp?.content;

  // Poll until READY if status is PENDING
  useEffect(() => {
    if (!lp || lp.status === "READY" || lp.status === "ERROR") return;
    const timer = setInterval(() => {
      fetch(`${API_URL}/api/v1/lesson-plans/${lpId}`, {
        headers: { "X-API-Key": getApiKey() },
      })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((data: LessonPlan) => setLp(data))
        .catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [lp, lpId]);

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-2xl bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-dars-rule-light shrink-0">
          <div>
            <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest">Lesson Plan</p>
            {lp && <p className="text-sm font-semibold text-dars-ink mt-0.5">{lp.topic}</p>}
          </div>
          <div className="flex items-center gap-3">
            {lp?.content_bilingual && (
              <button
                type="button"
                onClick={() => setBilingual((b) => !b)}
                className={`text-xs px-3 py-1.5 rounded-full border transition-colors cursor-pointer ${
                  bilingual
                    ? "bg-dars-terra text-white border-dars-terra"
                    : "bg-white text-dars-muted border-dars-rule-light hover:border-dars-terra hover:text-dars-terra"
                }`}
              >
                {bilingual ? "English" : "Bilingual"}
              </button>
            )}
            <button type="button" onClick={onClose} className="text-dars-muted hover:text-dars-ink cursor-pointer text-xl leading-none">✕</button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && <div className="flex justify-center py-16"><BookLoader size={40} label="Loading lesson plan" /></div>}
          {!loading && lp?.status === "PENDING" && (
            <div className="flex flex-col items-center gap-3 py-16">
              <BookLoader size={40} label="Generating lesson plan…" />
              <p className="text-xs text-dars-muted">This takes about 30 seconds</p>
            </div>
          )}
          {!loading && lp?.status === "ERROR" && (
            <p className="text-sm text-red-500">Generation failed. Try again.</p>
          )}
          {!loading && lp?.status === "READY" && !html && (
            <p className="text-sm text-dars-muted">No content available.</p>
          )}
          {!loading && lp?.status === "READY" && html && (
            <div
              className="text-sm text-dars-ink [&_h2]:font-bold [&_h2]:text-base [&_h2]:mt-5 [&_h2]:mb-2 [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-1 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_li]:mb-1 [&_table]:w-full [&_table]:text-xs [&_table]:border-collapse [&_td]:border [&_td]:border-dars-rule-light [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-dars-rule-light [&_th]:px-2 [&_th]:py-1 [&_th]:bg-dars-parchment [&_th]:font-semibold"
              dangerouslySetInnerHTML={{ __html: html }}
            />
          )}
        </div>
      </div>
    </>
  );
}

// ── Assessment Panel (slide-over) ─────────────────────────────────────────────

function AssessmentPanel({ assessmentId, onClose }: { assessmentId: string; onClose: () => void }) {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    fetch(`${API_URL}/api/v1/assessments/${assessmentId}`, {
      headers: { "X-API-Key": getApiKey() },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: Assessment) => setAssessment(data))
      .catch(() => { toast.error("Failed to load assessment"); })
      .finally(() => setLoading(false));
  }, [assessmentId]);

  useEffect(() => {
    if (!assessment || assessment.status === "READY" || assessment.status === "ERROR") return;
    const timer = setInterval(() => {
      fetch(`${API_URL}/api/v1/assessments/${assessmentId}`, {
        headers: { "X-API-Key": getApiKey() },
      })
        .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
        .then((data: Assessment) => setAssessment(data))
        .catch(() => {});
    }, 3000);
    return () => clearInterval(timer);
  }, [assessment, assessmentId]);

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-2xl bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-dars-rule-light shrink-0">
          <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest">Assessment</p>
          <button type="button" onClick={onClose} className="text-dars-muted hover:text-dars-ink cursor-pointer text-xl leading-none">✕</button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          {loading && <div className="flex justify-center py-16"><BookLoader size={40} label="Loading assessment" /></div>}
          {!loading && assessment?.status === "PENDING" && (
            <div className="flex flex-col items-center gap-3 py-16">
              <BookLoader size={40} label="Generating assessment…" />
              <p className="text-xs text-dars-muted">This takes about 15 seconds</p>
            </div>
          )}
          {!loading && assessment?.status === "ERROR" && (
            <p className="text-sm text-red-500">Generation failed. Try again.</p>
          )}
          {!loading && assessment?.status === "READY" && assessment.content && (
            <div
              className="text-sm text-dars-ink [&_.mcq]:mb-6 [&_.mcq_p]:mb-2 [&_.mcq_ul]:list-none [&_.mcq_ul]:pl-0 [&_.mcq_li]:py-0.5"
              dangerouslySetInnerHTML={{ __html: assessment.content }}
            />
          )}
        </div>
      </div>
    </>
  );
}

// ── Column header ─────────────────────────────────────────────────────────────

function ColHeader({ label }: { label: string }) {
  return (
    <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest px-4 py-3 border-b border-dars-rule-light">
      {label}
    </p>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="px-4 py-6 text-sm text-dars-muted">{message}</p>;
}

// ── Books column ──────────────────────────────────────────────────────────────

function BooksColumn({
  books, selectedId, onSelect, loading,
}: {
  books: Book[]; selectedId: string | null; onSelect: (b: Book) => void; loading: boolean;
}) {
  return (
    <div className="flex flex-col">
      <ColHeader label="Books" />
      {loading && <div className="px-4 py-8 flex justify-center"><BookLoader size={36} label="Loading books" /></div>}
      {!loading && books.length === 0 && <EmptyState message="Select curriculum, grade and subject." />}
      <ul>
        {books.map((book) => {
          const active = selectedId === book.id;
          return (
            <li key={book.id}>
              <button
                type="button"
                onClick={() => onSelect(book)}
                className={`w-full text-left px-4 py-3 border-b border-dars-rule-light transition-colors cursor-pointer border-x-0 border-t-0 ${active ? "bg-dars-terra text-white" : "bg-white hover:bg-dars-parchment text-dars-ink"}`}
              >
                <p className={`text-sm font-semibold leading-tight ${active ? "text-white" : "text-dars-ink"}`}>{book.title}</p>
                <p className={`text-xs mt-0.5 ${active ? "text-white/80" : "text-dars-muted"}`}>{book.curriculum} · Grade {book.grade} · {book.subject}</p>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Chapters column ───────────────────────────────────────────────────────────

function ChaptersColumn({
  chapters, selectedId, onSelect, loading, onGenerateAllLps, generatingAllLps,
}: {
  chapters: Chapter[];
  selectedId: string | null;
  onSelect: (c: Chapter) => void;
  loading: boolean;
  onGenerateAllLps: (chapterId: string) => void;
  generatingAllLps: string | null;
}) {
  const sorted = [...chapters].sort((a, b) => a.chapter_number - b.chapter_number);
  return (
    <div className="flex flex-col">
      <ColHeader label="Chapters" />
      {loading && <div className="px-4 py-8 flex justify-center"><BookLoader size={36} label="Loading chapters" /></div>}
      {!loading && sorted.length === 0 && <EmptyState message="Select a book to see chapters." />}
      <ul>
        {sorted.map((ch) => {
          const active = selectedId === ch.id;
          const pages = ch.start_page != null && ch.end_page != null ? `pp. ${ch.start_page}–${ch.end_page}` : null;
          const isGenerating = generatingAllLps === ch.id;
          return (
            <li key={ch.id}>
              <div className={`flex items-center border-b border-dars-rule-light ${active ? "bg-dars-terra" : "bg-white hover:bg-dars-parchment"}`}>
                <button
                  type="button"
                  onClick={() => onSelect(ch)}
                  className={`flex-1 text-left px-4 py-3 transition-colors cursor-pointer`}
                >
                  <div className="flex items-start gap-2">
                    <span className={`text-xs font-bold shrink-0 w-5 pt-0.5 ${active ? "text-white/80" : "text-dars-muted"}`}>{ch.chapter_number}</span>
                    <div className="min-w-0">
                      <p className={`text-sm font-semibold leading-tight ${active ? "text-white" : "text-dars-ink"}`}>{ch.title}</p>
                      {pages && <p className={`text-xs mt-0.5 ${active ? "text-white/80" : "text-dars-muted"}`}>{pages}</p>}
                    </div>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onGenerateAllLps(ch.id); }}
                  disabled={isGenerating}
                  title="Generate LPs for all slots in this chapter"
                  className={`shrink-0 flex items-center gap-0.5 text-[10px] font-semibold px-2 py-0.5 mr-2 rounded border disabled:opacity-60 cursor-pointer transition-colors ${active ? "border-white/60 text-white hover:bg-white/20" : "border-dars-terra text-dars-terra hover:bg-dars-terra hover:text-white"}`}
                >
                  {isGenerating ? <Spinner /> : "Gen All LPs"}
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Topics & Slots column ─────────────────────────────────────────────────────

function AddTopicForm({ chapterId, topicCount, onDone }: { chapterId: string; topicCount: number; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [startPage, setStartPage] = useState("");
  const [endPage, setEndPage] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim()) return;
    setSaving(true);
    try {
      const r = await fetch(`${API_URL}/api/v1/chapters/${chapterId}/topics`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
        body: JSON.stringify({
          chapter_id: chapterId,
          topic_number: topicCount + 1,
          title: title.trim(),
          start_page: startPage.trim() ? parseInt(startPage.trim()) : null,
          end_page: endPage.trim() ? parseInt(endPage.trim()) : null,
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setTitle(""); setStartPage(""); setEndPage("");
      onDone();
    } catch { toast.error("Failed to add topic."); }
    finally { setSaving(false); }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-end px-4 py-3 border-t border-dars-rule-light bg-dars-parchment">
      <div className="flex-1">
        <input
          value={title} onChange={(e) => setTitle(e.target.value)}
          placeholder="Topic title"
          className="w-full border border-dars-rule-light rounded px-2 py-1.5 text-xs text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        />
      </div>
      <input
        value={startPage} onChange={(e) => setStartPage(e.target.value)}
        placeholder="p. start"
        type="number"
        className="w-16 border border-dars-rule-light rounded px-2 py-1.5 text-xs text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
      />
      <input
        value={endPage} onChange={(e) => setEndPage(e.target.value)}
        placeholder="p. end"
        type="number"
        className="w-16 border border-dars-rule-light rounded px-2 py-1.5 text-xs text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
      />
      <button type="submit" disabled={saving || !title.trim()} className="flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded bg-dars-terra text-white hover:bg-dars-terra/90 disabled:opacity-50 cursor-pointer">
        {saving ? <Spinner /> : "Add"}
      </button>
    </form>
  );
}

function AddSlotForm({ topicId, dayCount, onDone }: { topicId: string; dayCount: number; onDone: () => void }) {
  const [subtopic, setSubtopic] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!subtopic.trim()) return;
    setSaving(true);
    try {
      const r = await fetch(`${API_URL}/api/v1/topics/${topicId}/slots`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
        body: JSON.stringify({ day_number: dayCount + 1, topic_subtopic: subtopic.trim() }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setSubtopic("");
      onDone();
    } catch { toast.error("Failed to add slot."); }
    finally { setSaving(false); }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-center mt-1 ml-7">
      <input
        value={subtopic} onChange={(e) => setSubtopic(e.target.value)}
        placeholder="Topic — Subtopic"
        className="flex-1 border border-dars-rule-light rounded px-2 py-1 text-xs text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
      />
      <button type="submit" disabled={saving || !subtopic.trim()} className="flex items-center gap-1 px-2.5 py-1 text-[10px] font-semibold rounded bg-dars-terra text-white hover:bg-dars-terra/90 disabled:opacity-50 cursor-pointer">
        {saving ? <Spinner /> : "+ Slot"}
      </button>
    </form>
  );
}

function TopicSlotsColumn({
  topics, slots, chapterSelected, selectedChapterId, loading, onViewLP, onViewAssessment, onSlotsRefresh,
}: {
  topics: Topic[];
  slots: Record<string, Slot[]>;
  chapterSelected: boolean;
  selectedChapterId: string | null;
  loading: boolean;
  onViewLP: (lpId: string) => void;
  onViewAssessment: (assessmentId: string) => void;
  onSlotsRefresh: () => void;
}) {
  const [breakingDown, setBreakingDown] = useState(false);
  const [deletingBreakdown, setDeletingBreakdown] = useState(false);
  const [generatingLp, setGeneratingLp] = useState<Record<string, boolean>>({});
  const [generatingAssessment, setGeneratingAssessment] = useState<Record<string, boolean>>({});
  const [deletingTopic, setDeletingTopic] = useState<Record<string, boolean>>({});
  const [deletingSlot, setDeletingSlot] = useState<Record<string, boolean>>({});
  const [deletingLp, setDeletingLp] = useState<Record<string, boolean>>({});
  const [addingSlotFor, setAddingSlotFor] = useState<string | null>(null);
  const [showAddTopic, setShowAddTopic] = useState(false);

  useEffect(() => { setBreakingDown(false); setShowAddTopic(false); setAddingSlotFor(null); }, [selectedChapterId]);

  const handleBreakdown = useCallback(async () => {
    if (!selectedChapterId) return;
    setBreakingDown(true);
    try {
      const r = await fetch(`${API_URL}/api/v1/chapters/${selectedChapterId}/breakdown`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
      });
      if (r.ok) onSlotsRefresh();
      else toast.error("Breakdown failed.");
    } catch { toast.error("Breakdown failed. Please try again."); }
    finally { setBreakingDown(false); }
  }, [selectedChapterId, onSlotsRefresh]);

  const handleDeleteBreakdown = useCallback(async () => {
    if (!selectedChapterId) return;
    if (!confirm("Delete all topics and slots for this chapter?")) return;
    setDeletingBreakdown(true);
    try {
      await fetch(`${API_URL}/api/v1/chapters/${selectedChapterId}/breakdown`, {
        method: "DELETE",
        headers: { "X-API-Key": getApiKey() },
      });
      onSlotsRefresh();
    } catch { toast.error("Failed to delete breakdown."); }
    finally { setDeletingBreakdown(false); }
  }, [selectedChapterId, onSlotsRefresh]);

  const handleDeleteTopic = useCallback(async (topicId: string) => {
    if (!confirm("Delete this topic and all its slots?")) return;
    setDeletingTopic((p) => ({ ...p, [topicId]: true }));
    try {
      await fetch(`${API_URL}/api/v1/topics/${topicId}`, { method: "DELETE", headers: { "X-API-Key": getApiKey() } });
      onSlotsRefresh();
    } catch { toast.error("Failed to delete topic."); }
    finally { setDeletingTopic((p) => ({ ...p, [topicId]: false })); }
  }, [onSlotsRefresh]);

  const handleDeleteSlot = useCallback(async (slotId: string) => {
    setDeletingSlot((p) => ({ ...p, [slotId]: true }));
    try {
      await fetch(`${API_URL}/api/v1/slots/${slotId}`, { method: "DELETE", headers: { "X-API-Key": getApiKey() } });
      onSlotsRefresh();
    } catch { toast.error("Failed to delete slot."); }
    finally { setDeletingSlot((p) => ({ ...p, [slotId]: false })); }
  }, [onSlotsRefresh]);

  const handleDeleteLp = useCallback(async (lpId: string, slotId: string) => {
    if (!confirm("Delete this lesson plan?")) return;
    setDeletingLp((p) => ({ ...p, [slotId]: true }));
    try {
      await fetch(`${API_URL}/api/v1/lesson-plans/${lpId}`, { method: "DELETE", headers: { "X-API-Key": getApiKey() } });
      onSlotsRefresh();
    } catch { toast.error("Failed to delete lesson plan."); }
    finally { setDeletingLp((p) => ({ ...p, [slotId]: false })); }
  }, [onSlotsRefresh]);

  const handleGenerateLp = useCallback(async (slotId: string) => {
    setGeneratingLp((prev) => ({ ...prev, [slotId]: true }));
    try {
      const r = await fetch(`${API_URL}/api/v1/slots/${slotId}/generate-lp`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
      });
      if (r.ok) {
        const data: LessonPlan = await r.json();
        onViewLP(data.id);
        onSlotsRefresh();
      }
    } catch { toast.error("Failed to generate lesson plan."); }
    finally { setGeneratingLp((prev) => ({ ...prev, [slotId]: false })); }
  }, [onViewLP, onSlotsRefresh]);

  const handleGenerateAssessment = useCallback(async (lpId: string) => {
    setGeneratingAssessment((prev) => ({ ...prev, [lpId]: true }));
    try {
      const r = await fetch(`${API_URL}/api/v1/lesson-plans/${lpId}/assessment`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
      });
      if (r.ok) {
        const data: Assessment = await r.json();
        onViewAssessment(data.id);
      } else {
        toast.error("Failed to generate assessment.");
      }
    } catch { toast.error("Failed to generate assessment."); }
    finally { setGeneratingAssessment((prev) => ({ ...prev, [lpId]: false })); }
  }, [onViewAssessment]);

  if (!chapterSelected) {
    return (
      <div className="flex flex-col">
        <ColHeader label="Topics & Slots" />
        <EmptyState message="Select a chapter to see topics." />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col">
        <ColHeader label="Topics & Slots" />
        <div className="px-4 py-8 flex justify-center"><BookLoader size={36} label="Loading topics" /></div>
      </div>
    );
  }

  if (topics.length === 0) {
    return (
      <div className="flex flex-col">
        <ColHeader label="Topics & Slots" />
        <div className="px-4 py-6 flex flex-col gap-3">
          <p className="text-sm text-dars-muted">No breakdown yet for this chapter.</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleBreakdown}
              disabled={breakingDown}
              className="flex items-center gap-2 px-4 py-2 rounded-md bg-dars-terra text-white text-sm font-semibold hover:bg-dars-terra/90 disabled:opacity-60 cursor-pointer transition-colors"
            >
              {breakingDown ? <><Spinner /> Generating…</> : "Generate AI Breakdown"}
            </button>
            <button
              type="button"
              onClick={() => setShowAddTopic(true)}
              className="px-4 py-2 rounded-md border border-dars-terra text-dars-terra text-sm font-semibold hover:bg-dars-terra/5 cursor-pointer transition-colors"
            >
              + Add manually
            </button>
          </div>
        </div>
        {showAddTopic && selectedChapterId && (
          <AddTopicForm chapterId={selectedChapterId} topicCount={0} onDone={() => { setShowAddTopic(false); onSlotsRefresh(); }} />
        )}
      </div>
    );
  }

  const sorted = [...topics].sort((a, b) => a.topic_number - b.topic_number);
  const allSlots = Object.values(slots).flat();

  return (
    <div className="flex flex-col">
      <div className="flex items-center justify-between pr-3 border-b border-dars-rule-light">
        <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest px-4 py-3">Topics & Slots</p>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setShowAddTopic((v) => !v)}
            className="text-[10px] font-semibold text-dars-muted hover:text-dars-terra cursor-pointer transition-colors"
          >
            + Topic
          </button>
          <button
            type="button"
            onClick={handleBreakdown}
            disabled={breakingDown}
            title="Regenerate breakdown (overwrites existing)"
            className="flex items-center gap-1 text-[10px] font-semibold text-dars-muted hover:text-dars-terra disabled:opacity-50 cursor-pointer transition-colors"
          >
            {breakingDown ? <Spinner /> : "↺"} Regenerate
          </button>
          <button
            type="button"
            onClick={handleDeleteBreakdown}
            disabled={deletingBreakdown}
            title="Delete all topics and slots"
            className="flex items-center gap-1 text-[10px] font-semibold text-red-400 hover:text-red-600 disabled:opacity-50 cursor-pointer transition-colors"
          >
            {deletingBreakdown ? <Spinner /> : "✕"} Clear
          </button>
        </div>
      </div>
      <ul>
        {sorted.map((topic) => {
          const topicSlots = slots[topic.id] ?? [];
          const isAddingSlot = addingSlotFor === topic.id;
          return (
            <li key={topic.id} className="border-b border-dars-rule-light last:border-0">
              <div className="px-4 py-3">
                <div className="flex items-start gap-2 mb-2">
                  <span className="text-xs font-bold text-dars-muted shrink-0 w-5 pt-0.5">{topic.topic_number}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-dars-ink leading-tight">{topic.title}</p>
                    {topic.start_page != null && (
                      <p className="text-xs text-dars-muted mt-0.5">
                        pp. {topic.start_page}{topic.end_page != null && topic.end_page !== topic.start_page ? `–${topic.end_page}` : ""}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={() => setAddingSlotFor(isAddingSlot ? null : topic.id)}
                      title="Add slot manually"
                      className="text-[10px] font-semibold text-dars-muted hover:text-dars-terra cursor-pointer transition-colors"
                    >
                      + slot
                    </button>
                    <button
                      type="button"
                      onClick={() => handleDeleteTopic(topic.id)}
                      disabled={!!deletingTopic[topic.id]}
                      title="Delete topic and its slots"
                      className="text-[10px] text-red-300 hover:text-red-500 disabled:opacity-50 cursor-pointer transition-colors"
                    >
                      {deletingTopic[topic.id] ? <Spinner /> : "✕"}
                    </button>
                  </div>
                </div>

                {topicSlots.length > 0 && (
                  <ul className="ml-7 space-y-1">
                    {topicSlots.map((slot) => (
                      <li key={slot.id} className="flex items-start gap-2 bg-dars-parchment border border-dars-rule-light rounded-md px-2.5 py-1.5">
                        <span className="text-[10px] font-bold text-dars-muted shrink-0 pt-0.5 w-4">D{slot.day_number}</span>
                        <div className="min-w-0 flex-1">
                          <p className="text-xs text-dars-ink leading-tight">{slot.topic_subtopic}</p>
                          {slot.scheduled_date && (
                            <p className="text-[10px] text-dars-muted mt-0.5">
                              {new Date(slot.scheduled_date + "T00:00:00").toLocaleDateString("en-PK", { day: "numeric", month: "short", year: "numeric" })}
                            </p>
                          )}
                        </div>
                        <div className="shrink-0 flex items-center gap-1">
                          {slot.lesson_plan_id && (
                            <>
                              <button
                                type="button"
                                onClick={() => onViewLP(slot.lesson_plan_id!)}
                                className="text-[10px] font-semibold px-2 py-0.5 rounded bg-dars-terra text-white hover:bg-dars-terra/90 cursor-pointer transition-colors"
                              >
                                LP
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeleteLp(slot.lesson_plan_id!, slot.id)}
                                disabled={!!deletingLp[slot.id]}
                                title="Delete lesson plan"
                                className="text-[10px] text-red-300 hover:text-red-500 disabled:opacity-50 cursor-pointer transition-colors"
                              >
                                {deletingLp[slot.id] ? <Spinner /> : "✕"}
                              </button>
                            </>
                          )}
                          <button
                            type="button"
                            onClick={() => handleGenerateLp(slot.id)}
                            disabled={!!generatingLp[slot.id]}
                            title={slot.lesson_plan_id ? "Regenerate LP" : "Generate LP"}
                            className="flex items-center gap-0.5 text-[10px] font-semibold px-2 py-0.5 rounded border border-dars-terra text-dars-terra hover:bg-dars-terra hover:text-white disabled:opacity-60 cursor-pointer transition-colors"
                          >
                            {generatingLp[slot.id] ? <Spinner /> : slot.lesson_plan_id ? "↺" : "Gen LP"}
                          </button>
                          {slot.lesson_plan_id && (
                            <button
                              type="button"
                              onClick={() => handleGenerateAssessment(slot.lesson_plan_id!)}
                              disabled={!!generatingAssessment[slot.lesson_plan_id!]}
                              title="Generate Assessment"
                              className="flex items-center gap-0.5 text-[10px] font-semibold px-2 py-0.5 rounded border border-dars-ink/30 text-dars-ink/60 hover:bg-dars-ink hover:text-white disabled:opacity-60 cursor-pointer transition-colors"
                            >
                              {generatingAssessment[slot.lesson_plan_id!] ? <Spinner /> : "Quiz"}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => handleDeleteSlot(slot.id)}
                            disabled={!!deletingSlot[slot.id]}
                            title="Delete slot"
                            className="text-[10px] text-red-300 hover:text-red-500 disabled:opacity-50 cursor-pointer transition-colors"
                          >
                            {deletingSlot[slot.id] ? <Spinner /> : "✕"}
                          </button>
                        </div>
                      </li>
                    ))}
                  </ul>
                )}

                {isAddingSlot && (
                  <AddSlotForm
                    topicId={topic.id}
                    dayCount={allSlots.length}
                    onDone={() => { setAddingSlotFor(null); onSlotsRefresh(); }}
                  />
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {showAddTopic && selectedChapterId && (
        <AddTopicForm
          chapterId={selectedChapterId}
          topicCount={topics.length}
          onDone={() => { setShowAddTopic(false); onSlotsRefresh(); }}
        />
      )}
    </div>
  );
}

const GRADES = [1, 2, 3, 4, 5];
const SUBJECTS = ["Eng", "Maths", "Urdu"];
const CURRICULUMS = ["ICT", "Punjab"];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function CurriculumPage() {
  const router = useRouter();
  useEffect(() => {
    if (!isAdmin()) router.replace("/dashboard/lesson-plans");
  }, [router]);

  const [curriculum, setCurriculum] = useState<string | null>(null);
  const [grade, setGrade] = useState<number | null>(null);
  const [subject, setSubject] = useState<string | null>(null);
  const [books, setBooks] = useState<Book[]>([]);
  const [loadingBooks, setLoadingBooks] = useState(false);
  const [selectedBook, setSelectedBook] = useState<Book | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loadingChapters, setLoadingChapters] = useState(false);
  const [selectedChapter, setSelectedChapter] = useState<Chapter | null>(null);
  const [topics, setTopics] = useState<Topic[]>([]);
  const [loadingTopics, setLoadingTopics] = useState(false);
  const [slots, setSlots] = useState<Record<string, Slot[]>>({});
  const [activeLpId, setActiveLpId] = useState<string | null>(null);
  const [activeAssessmentId, setActiveAssessmentId] = useState<string | null>(null);

  // Bulk LP generation state
  const [generatingAllLps, setGeneratingAllLps] = useState<string | null>(null);

  useEffect(() => {
    if (curriculum === null || grade === null || subject === null) {
      setBooks([]); setSelectedBook(null); setChapters([]); setSelectedChapter(null); setTopics([]); setSlots({});
      return;
    }
    setLoadingBooks(true);
    setBooks([]); setSelectedBook(null); setChapters([]); setSelectedChapter(null); setTopics([]); setSlots({});
    fetch(`${API_URL}/api/v1/books?curriculum=${encodeURIComponent(curriculum)}&grade=${grade}&subject=${encodeURIComponent(subject)}`, {
      headers: { "X-API-Key": getApiKey() },
    })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: { items: Book[] }) => setBooks(data.items ?? []))
      .catch(() => { toast.error("Failed to load data."); })
      .finally(() => setLoadingBooks(false));
  }, [curriculum, grade, subject]);

  const handleSelectBook = useCallback((book: Book) => {
    setSelectedBook(book); setChapters([]); setSelectedChapter(null); setTopics([]); setSlots({});
    setLoadingChapters(true);
    fetch(`${API_URL}/api/v1/books/${book.id}/chapters`, { headers: { "X-API-Key": getApiKey() } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data: { items: Chapter[] }) => setChapters(data.items ?? []))
      .catch(() => { toast.error("Failed to load data."); })
      .finally(() => setLoadingChapters(false));
  }, []);

  const loadTopicsAndSlots = useCallback((book: Book, chapter: Chapter) => {
    setTopics([]); setSlots({}); setLoadingTopics(true);
    const apiKey = getApiKey();
    fetch(`${API_URL}/api/v1/books/${book.id}/chapters/${chapter.id}/topics`, { headers: { "X-API-Key": apiKey } })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(async (data: { items: Topic[] }) => {
        const fetchedTopics = data.items ?? [];
        setTopics(fetchedTopics);
        const slotResults = await Promise.all(
          fetchedTopics.map((t) =>
            fetch(`${API_URL}/api/v1/topics/${t.id}/slots`, { headers: { "X-API-Key": apiKey } })
              .then((r) => (r.ok ? r.json() : Promise.resolve({ items: [] })))
              .then((d: { items: Slot[] }) => ({ topicId: t.id, slots: d.items ?? [] }))
              .catch(() => ({ topicId: t.id, slots: [] }))
          )
        );
        const slotMap: Record<string, Slot[]> = {};
        for (const { topicId, slots: s } of slotResults) slotMap[topicId] = s;
        setSlots(slotMap);
      })
      .catch(() => { toast.error("Failed to load data."); })
      .finally(() => setLoadingTopics(false));
  }, []);

  const handleSelectChapter = useCallback((chapter: Chapter) => {
    setSelectedChapter(chapter);
    if (selectedBook) loadTopicsAndSlots(selectedBook, chapter);
  }, [selectedBook, loadTopicsAndSlots]);

  const handleSlotsRefresh = useCallback(() => {
    if (selectedBook && selectedChapter) loadTopicsAndSlots(selectedBook, selectedChapter);
  }, [selectedBook, selectedChapter, loadTopicsAndSlots]);

  const handleGenerateAllLps = useCallback(async (chapterId: string) => {
    setGeneratingAllLps(chapterId);
    try {
      await fetch(`${API_URL}/admin/chapters/${chapterId}/generate-lps`, {
        method: "POST",
        headers: { "X-API-Key": getApiKey(), "Content-Type": "application/json" },
      });
    } catch { toast.error("Failed to start bulk LP generation."); }
    finally { setGeneratingAllLps(null); }
  }, []);

  return (
    <div className="p-8 max-w-6xl">
      <h1 className="font-serif text-2xl font-bold text-dars-ink mb-6">Curriculum</h1>

      <div className="flex items-center gap-4 mb-6">
        <select
          value={curriculum ?? ""}
          onChange={(e) => setCurriculum(e.target.value || null)}
          className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        >
          <option value="">Curriculum</option>
          {CURRICULUMS.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select
          value={grade ?? ""}
          onChange={(e) => setGrade(e.target.value ? Number(e.target.value) : null)}
          className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        >
          <option value="">Grade</option>
          {GRADES.map((g) => <option key={g} value={g}>Grade {g}</option>)}
        </select>
        <select
          value={subject ?? ""}
          onChange={(e) => setSubject(e.target.value || null)}
          className="border border-dars-rule-light rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
        >
          <option value="">Subject</option>
          {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="border border-dars-rule-light rounded-lg overflow-hidden grid grid-cols-3 divide-x divide-dars-rule-light bg-white min-h-[400px]">
        <BooksColumn books={books} selectedId={selectedBook?.id ?? null} onSelect={handleSelectBook} loading={loadingBooks} />
        <ChaptersColumn
          chapters={chapters}
          selectedId={selectedChapter?.id ?? null}
          onSelect={handleSelectChapter}
          loading={loadingChapters}
          onGenerateAllLps={handleGenerateAllLps}
          generatingAllLps={generatingAllLps}
        />
        <TopicSlotsColumn
          topics={topics}
          slots={slots}
          chapterSelected={selectedChapter !== null}
          selectedChapterId={selectedChapter?.id ?? null}
          loading={loadingTopics}
          onViewLP={setActiveLpId}
          onViewAssessment={setActiveAssessmentId}
          onSlotsRefresh={handleSlotsRefresh}
        />
      </div>

      {activeLpId && <LPPanel lpId={activeLpId} onClose={() => setActiveLpId(null)} />}
      {activeAssessmentId && <AssessmentPanel assessmentId={activeAssessmentId} onClose={() => setActiveAssessmentId(null)} />}
    </div>
  );
}
