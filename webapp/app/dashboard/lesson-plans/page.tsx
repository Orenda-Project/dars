"use client";

import { useEffect, useRef, useState } from "react";

interface Session {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
}

interface Teacher {
  id: string;
  name: string;
  email: string | null;
}

interface TeacherListResponse {
  items: Teacher[];
  total: number;
  limit: number;
  offset: number;
}

interface LessonPlan {
  id: string;
  status: "PENDING" | "READY" | "ERROR";
  grade: string;
  subject: string;
  topic?: string | null;
  created_at: string;
  content?: string | null;
}

interface LessonPlanListResponse {
  items: LessonPlan[];
  total: number;
  limit: number;
  offset: number;
}

interface ReviewResult {
  [key: string]: unknown;
}

interface FormState {
  grade: string;
  subject: string;
  page_number: string;
  curriculum: string;
  topic: string;
  class_strength: string;
  exercise_page_number: string;
  custom_prompt: string;
  generate_bilingual: boolean;
}

const DEFAULT_FORM: FormState = {
  grade: "",
  subject: "",
  page_number: "",
  curriculum: "ICT",
  topic: "",
  class_strength: "",
  exercise_page_number: "",
  custom_prompt: "",
  generate_bilingual: false,
};

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString("en-PK", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function StatusBadge({ status }: { status: LessonPlan["status"] }) {
  const classes =
    status === "READY"
      ? "bg-green-100 text-green-800"
      : status === "ERROR"
        ? "bg-red-100 text-red-800"
        : "bg-yellow-100 text-yellow-800";
  return (
    <span
      className={`inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded ${classes}`}
    >
      {status}
    </span>
  );
}

function ReviewDisplay({ data }: { data: ReviewResult }) {
  return (
    <div className="mt-4 space-y-3">
      {Object.entries(data).map(([key, value]) => (
        <div key={key} className="border border-dars-rule-light rounded-md p-3 bg-dars-parchment">
          <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide mb-1">
            {key.replace(/_/g, " ")}
          </p>
          {typeof value === "string" || typeof value === "number" ? (
            <p className="text-sm text-dars-ink">{String(value)}</p>
          ) : (
            <pre className="text-xs font-mono text-dars-ink whitespace-pre-wrap break-words">
              {JSON.stringify(value, null, 2)}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}

export default function LessonPlansPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const [session, setSession] = useState<Session | null>(null);

  // --- Teacher selector state ---
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [teachersLoading, setTeachersLoading] = useState(false);
  const [teacherSearch, setTeacherSearch] = useState("");
  const [selectedTeacher, setSelectedTeacher] = useState<Teacher | null>(null);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const teacherSearchDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // --- Generate form state ---
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generatedLP, setGeneratedLP] = useState<LessonPlan | null>(null);
  const generatedRef = useRef<HTMLDivElement>(null);

  // --- Past LPs state ---
  const [lpList, setLpList] = useState<LessonPlan[]>([]);
  const [lpTotal, setLpTotal] = useState(0);
  const [lpOffset, setLpOffset] = useState(0);
  const [lpLoading, setLpLoading] = useState(false);
  const [lpError, setLpError] = useState<string | null>(null);
  const LP_LIMIT = 10;

  // --- Expanded card state ---
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reviewLoading, setReviewLoading] = useState<Record<string, boolean>>({});
  const [reviewData, setReviewData] = useState<Record<string, ReviewResult>>({});
  const [reviewError, setReviewError] = useState<Record<string, string>>({});

  // --- Auth ---
  useEffect(() => {
    const raw = localStorage.getItem("dars_session");
    if (!raw) {
      window.location.href = "/login";
      return;
    }
    setSession(JSON.parse(raw) as Session);
  }, []);

  // --- Close dropdown on outside click ---
  useEffect(() => {
    function handleOutsideClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  // --- Fetch teachers for selector ---
  function fetchTeachers(apiKey: string, query: string) {
    setTeachersLoading(true);
    const params = new URLSearchParams({ limit: "20", offset: "0" });
    if (query) params.set("search", query);
    fetch(`${apiBase}/api/v1/teachers?${params.toString()}`, {
      headers: { "X-API-Key": apiKey },
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem("dars_session");
            window.location.href = "/login";
            return;
          }
          throw new Error("Failed to fetch teachers.");
        }
        const data = (await res.json()) as TeacherListResponse;
        setTeachers(data.items);
        setTeachersLoading(false);
      })
      .catch(() => {
        setTeachersLoading(false);
      });
  }

  useEffect(() => {
    if (!session) return;
    fetchTeachers(session.api_key, "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session]);

  function handleTeacherSearchChange(value: string) {
    setTeacherSearch(value);
    if (teacherSearchDebounceRef.current) clearTimeout(teacherSearchDebounceRef.current);
    if (!session) return;
    teacherSearchDebounceRef.current = setTimeout(() => {
      fetchTeachers(session.api_key, value.trim());
    }, 300);
  }

  function handleSelectTeacher(teacher: Teacher) {
    setSelectedTeacher(teacher);
    setDropdownOpen(false);
    setTeacherSearch("");
    // Reset LP list to page 1 for newly selected teacher
    setLpOffset(0);
    setGeneratedLP(null);
    setExpandedId(null);
  }

  // --- Fetch LP list ---
  function fetchLPs(offset: number, apiKey: string, teacherId: string) {
    setLpLoading(true);
    setLpError(null);
    const params = new URLSearchParams({
      limit: String(LP_LIMIT),
      offset: String(offset),
      teacher_id: teacherId,
    });
    fetch(`${apiBase}/api/v1/lesson-plans?${params.toString()}`, {
      headers: { "X-API-Key": apiKey },
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem("dars_session");
            window.location.href = "/login";
            return;
          }
          throw new Error("Failed to fetch lesson plans.");
        }
        const data = (await res.json()) as LessonPlanListResponse;
        setLpList(data.items);
        setLpTotal(data.total);
        setLpLoading(false);
      })
      .catch((err: unknown) => {
        setLpError(err instanceof Error ? err.message : "An unexpected error occurred.");
        setLpLoading(false);
      });
  }

  useEffect(() => {
    if (!session || !selectedTeacher) return;
    fetchLPs(lpOffset, session.api_key, selectedTeacher.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, selectedTeacher, lpOffset]);

  // --- Generate LP ---
  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!session || !selectedTeacher) return;
    setGenerating(true);
    setGenerateError(null);
    setGeneratedLP(null);

    const body: Record<string, unknown> = {
      grade: form.grade,
      subject: form.subject,
      page_number: form.page_number,
      curriculum: form.curriculum,
      generate_bilingual: form.generate_bilingual,
    };
    if (form.topic) body.topic = form.topic;
    if (form.class_strength) body.class_strength = Number(form.class_strength);
    if (form.exercise_page_number) body.exercise_page_number = form.exercise_page_number;
    if (form.custom_prompt) body.custom_prompt = form.custom_prompt;

    try {
      const createRes = await fetch(`${apiBase}/api/v1/lesson-plans`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": session.api_key,
          "X-Teacher-ID": selectedTeacher.id,
        },
        body: JSON.stringify(body),
      });

      if (!createRes.ok) {
        if (createRes.status === 401) {
          localStorage.removeItem("dars_session");
          window.location.href = "/login";
          return;
        }
        const errData = await createRes.json().catch(() => ({}));
        throw new Error(
          (errData as { detail?: string }).detail ?? "Failed to create lesson plan.",
        );
      }

      const created = (await createRes.json()) as LessonPlan;
      const lpId = created.id;

      // Poll until READY or ERROR
      const maxWaitMs = 60_000;
      const intervalMs = 3_000;
      const deadline = Date.now() + maxWaitMs;

      const poll = async (): Promise<void> => {
        if (Date.now() > deadline) {
          throw new Error("Lesson plan generation timed out. Please try again.");
        }

        const pollRes = await fetch(`${apiBase}/api/v1/lesson-plans/${lpId}`, {
          headers: { "X-API-Key": session.api_key },
        });

        if (!pollRes.ok) throw new Error("Failed to poll lesson plan status.");

        const lp = (await pollRes.json()) as LessonPlan;

        if (lp.status === "READY") {
          setGeneratedLP(lp);
          setGenerating(false);
          // Refresh list
          fetchLPs(lpOffset, session.api_key, selectedTeacher.id);
          setTimeout(() => {
            generatedRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
          }, 100);
          return;
        }

        if (lp.status === "ERROR") {
          throw new Error("Lesson plan generation failed. Please try again.");
        }

        await new Promise<void>((resolve) => setTimeout(resolve, intervalMs));
        return poll();
      };

      await poll();
    } catch (err: unknown) {
      setGenerateError(err instanceof Error ? err.message : "An unexpected error occurred.");
      setGenerating(false);
    }
  }

  // --- Review LP ---
  async function handleReview(lpId: string) {
    if (!session) return;
    setReviewLoading((prev) => ({ ...prev, [lpId]: true }));
    setReviewError((prev) => ({ ...prev, [lpId]: "" }));

    try {
      const res = await fetch(`${apiBase}/api/v1/lesson-plans/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": session.api_key,
        },
        body: JSON.stringify({ lesson_plan_id: lpId }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(
          (errData as { detail?: string }).detail ?? "Failed to review lesson plan.",
        );
      }

      const data = (await res.json()) as ReviewResult;
      setReviewData((prev) => ({ ...prev, [lpId]: data }));
    } catch (err: unknown) {
      setReviewError((prev) => ({
        ...prev,
        [lpId]: err instanceof Error ? err.message : "An unexpected error occurred.",
      }));
    } finally {
      setReviewLoading((prev) => ({ ...prev, [lpId]: false }));
    }
  }

  const totalPages = Math.ceil(lpTotal / LP_LIMIT);
  const currentPage = Math.floor(lpOffset / LP_LIMIT) + 1;
  const isGated = !selectedTeacher;

  return (
    <div className="p-8 max-w-4xl">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="text-2xl font-serif font-bold text-dars-ink">Lesson Plans</h1>
        {session && (
          <p className="text-sm text-dars-muted mt-1">
            {session.name} &middot; {session.email}
          </p>
        )}
      </div>

      {/* Teacher selector */}
      <section className="mb-8">
        <label className="block text-xs font-semibold text-dars-muted mb-2 uppercase tracking-wide">
          Teacher <span className="text-dars-terra">*</span>
        </label>
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => {
              setDropdownOpen((v) => !v);
              if (!dropdownOpen && session) fetchTeachers(session.api_key, teacherSearch);
            }}
            className="w-full sm:w-96 flex items-center justify-between border border-dars-rule-dark rounded-md px-3 py-2 text-sm bg-white text-dars-ink hover:border-dars-terra focus:outline-none focus:ring-1 focus:ring-dars-terra transition-colors cursor-pointer"
          >
            {selectedTeacher ? (
              <span className="font-medium">
                {selectedTeacher.name}
                {selectedTeacher.email && (
                  <span className="font-normal text-dars-muted ml-1.5">
                    &middot; {selectedTeacher.email}
                  </span>
                )}
              </span>
            ) : (
              <span className="text-dars-muted">Select a teacher...</span>
            )}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`h-4 w-4 text-dars-muted shrink-0 ml-2 transition-transform ${dropdownOpen ? "rotate-180" : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>

          {dropdownOpen && (
            <div className="absolute z-20 mt-1 w-full sm:w-96 bg-white border border-dars-rule-dark rounded-md shadow-lg overflow-hidden">
              <div className="p-2 border-b border-dars-rule-light">
                <input
                  autoFocus
                  type="search"
                  value={teacherSearch}
                  onChange={(e) => handleTeacherSearchChange(e.target.value)}
                  placeholder="Search by name or email..."
                  className="w-full px-2 py-1.5 text-sm text-dars-ink border border-dars-rule-dark rounded-md bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                />
              </div>
              <ul className="max-h-56 overflow-y-auto">
                {teachersLoading && (
                  <li className="px-3 py-3 text-sm text-dars-muted animate-pulse">
                    Loading teachers...
                  </li>
                )}
                {!teachersLoading && teachers.length === 0 && (
                  <li className="px-3 py-3 text-sm text-dars-muted">No teachers found.</li>
                )}
                {!teachersLoading &&
                  teachers.map((t) => (
                    <li key={t.id}>
                      <button
                        type="button"
                        onClick={() => handleSelectTeacher(t)}
                        className={`w-full text-left px-3 py-2.5 text-sm hover:bg-dars-parchment transition-colors cursor-pointer border-none bg-transparent ${
                          selectedTeacher?.id === t.id ? "bg-dars-parchment font-semibold" : ""
                        }`}
                      >
                        <span className="font-medium text-dars-ink">{t.name}</span>
                        {t.email && (
                          <span className="text-dars-muted ml-1.5 text-xs">{t.email}</span>
                        )}
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* Teacher context banner — shown when a teacher is selected */}
      {selectedTeacher && (
        <div className="mb-8 flex items-center gap-3 px-4 py-3 bg-dars-parchment border border-dars-terra/30 rounded-lg">
          <div className="shrink-0 w-8 h-8 rounded-full bg-dars-terra/10 flex items-center justify-center">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 text-dars-terra"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
          </div>
          <div>
            <p className="text-xs font-semibold text-dars-muted uppercase tracking-wide">
              Generating for
            </p>
            <p className="text-sm font-semibold text-dars-ink">
              {selectedTeacher.name}
              {selectedTeacher.email && (
                <span className="font-normal text-dars-muted ml-1.5">{selectedTeacher.email}</span>
              )}
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setSelectedTeacher(null);
              setLpList([]);
              setLpTotal(0);
              setGeneratedLP(null);
            }}
            className="ml-auto text-xs text-dars-muted hover:text-dars-ink transition-colors cursor-pointer"
          >
            Change
          </button>
        </div>
      )}

      {/* Gated content wrapper */}
      <div className={isGated ? "opacity-40 pointer-events-none select-none" : undefined}>
        {/* Gate message — only visible when no teacher selected */}
        {isGated && (
          <div className="mb-6 flex items-center gap-2 px-4 py-3 bg-dars-parchment border border-dars-rule-dark rounded-lg">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-4 w-4 text-dars-muted shrink-0"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            <p className="text-sm text-dars-muted">
              Select a teacher above to get started.
            </p>
          </div>
        )}

        {/* Section A: Generate form */}
        <section className="mb-12">
          <h2 className="text-lg font-serif font-semibold text-dars-ink mb-4">
            Generate a Lesson Plan
          </h2>
          <form
            onSubmit={handleGenerate}
            className="border border-dars-rule-light rounded-lg bg-dars-parchment p-6 space-y-5"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Grade */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Grade <span className="text-dars-terra">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.grade}
                  onChange={(e) => setForm((f) => ({ ...f, grade: e.target.value }))}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="e.g. 5"
                />
              </div>

              {/* Subject */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Subject <span className="text-dars-terra">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.subject}
                  onChange={(e) => setForm((f) => ({ ...f, subject: e.target.value }))}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="e.g. Mathematics"
                />
              </div>

              {/* Page Number */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Page Number <span className="text-dars-terra">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.page_number}
                  onChange={(e) => setForm((f) => ({ ...f, page_number: e.target.value }))}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="e.g. 42"
                />
              </div>

              {/* Curriculum */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Curriculum <span className="text-dars-terra">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={form.curriculum}
                  onChange={(e) => setForm((f) => ({ ...f, curriculum: e.target.value }))}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="e.g. ICT"
                />
              </div>

              {/* Topic */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Topic
                </label>
                <input
                  type="text"
                  value={form.topic}
                  onChange={(e) => setForm((f) => ({ ...f, topic: e.target.value }))}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="Optional"
                />
              </div>

              {/* Class Strength */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Class Strength
                </label>
                <input
                  type="number"
                  min={1}
                  value={form.class_strength}
                  onChange={(e) => setForm((f) => ({ ...f, class_strength: e.target.value }))}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="Optional"
                />
              </div>

              {/* Exercise Page Number */}
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                  Exercise Page Number
                </label>
                <input
                  type="text"
                  value={form.exercise_page_number}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, exercise_page_number: e.target.value }))
                  }
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  placeholder="Optional"
                />
              </div>
            </div>

            {/* Custom Prompt */}
            <div>
              <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
                Custom Prompt
              </label>
              <textarea
                rows={3}
                value={form.custom_prompt}
                onChange={(e) => setForm((f) => ({ ...f, custom_prompt: e.target.value }))}
                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra resize-y"
                placeholder="Optional additional instructions..."
              />
            </div>

            {/* Generate Bilingual toggle */}
            <div className="flex items-center gap-3">
              <button
                type="button"
                role="switch"
                aria-checked={form.generate_bilingual}
                onClick={() =>
                  setForm((f) => ({ ...f, generate_bilingual: !f.generate_bilingual }))
                }
                className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                  form.generate_bilingual ? "bg-dars-terra" : "bg-dars-rule-dark"
                }`}
              >
                <span
                  className={`pointer-events-none inline-block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${
                    form.generate_bilingual ? "translate-x-4" : "translate-x-0"
                  }`}
                />
              </button>
              <span className="text-sm text-dars-ink">Generate Bilingual</span>
            </div>

            {generateError && (
              <p className="text-sm text-red-600 border border-red-200 rounded-md px-3 py-2 bg-red-50">
                {generateError}
              </p>
            )}

            <button
              type="submit"
              disabled={generating || isGated}
              className="px-5 py-2.5 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            >
              {generating ? "Generating your lesson plan..." : "Generate Lesson Plan"}
            </button>
          </form>

          {/* Generated LP output */}
          {generatedLP && generatedLP.content && (
            <div ref={generatedRef} className="mt-6">
              <div className="flex items-center gap-3 mb-3">
                <h3 className="text-base font-serif font-semibold text-dars-ink">
                  Generated Lesson Plan
                </h3>
                <StatusBadge status={generatedLP.status} />
              </div>
              <div
                className="border border-dars-rule-light rounded-lg bg-white p-6 prose prose-sm max-w-none overflow-auto"
                dangerouslySetInnerHTML={{ __html: generatedLP.content }}
              />
            </div>
          )}
        </section>

        {/* Section B: Past lesson plans */}
        <section>
          <h2 className="text-lg font-serif font-semibold text-dars-ink mb-4">
            Past Lesson Plans
          </h2>

          {lpLoading && (
            <p className="text-sm text-dars-muted animate-pulse">Loading lesson plans...</p>
          )}

          {lpError && (
            <p className="text-sm text-red-600 border border-red-200 rounded-md px-3 py-2 bg-red-50">
              {lpError}
            </p>
          )}

          {!lpLoading && !lpError && lpList.length === 0 && (
            <p className="text-sm text-dars-muted">
              {selectedTeacher
                ? `No lesson plans found for ${selectedTeacher.name}. Generate the first one above.`
                : "No lesson plans found. Generate your first one above."}
            </p>
          )}

          {!lpLoading && lpList.length > 0 && (
            <div className="space-y-3">
              {lpList.map((lp) => {
                const isExpanded = expandedId === lp.id;
                return (
                  <div
                    key={lp.id}
                    className="border border-dars-rule-light rounded-lg bg-dars-parchment overflow-hidden"
                  >
                    {/* Card header — click to expand/collapse */}
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : lp.id)}
                      className="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-dars-parchment-mid transition-colors cursor-pointer bg-transparent border-none"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-semibold text-dars-ink">
                            {lp.subject} — Grade {lp.grade}
                          </span>
                          {lp.topic && (
                            <span className="text-xs text-dars-muted">&middot; {lp.topic}</span>
                          )}
                          <StatusBadge status={lp.status} />
                        </div>
                        <p className="text-xs text-dars-muted mt-0.5">{formatDate(lp.created_at)}</p>
                      </div>
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className={`h-4 w-4 text-dars-muted shrink-0 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <polyline points="6 9 12 15 18 9" />
                      </svg>
                    </button>

                    {/* Expanded content */}
                    {isExpanded && (
                      <div className="border-t border-dars-rule-light px-5 py-5 bg-white">
                        {lp.content ? (
                          <div
                            className="prose prose-sm max-w-none overflow-auto"
                            dangerouslySetInnerHTML={{ __html: lp.content }}
                          />
                        ) : (
                          <p className="text-sm text-dars-muted italic">No content available.</p>
                        )}

                        {/* Review button */}
                        <div className="mt-5 pt-4 border-t border-dars-rule-light">
                          <button
                            type="button"
                            onClick={() => handleReview(lp.id)}
                            disabled={!!reviewLoading[lp.id]}
                            className="px-4 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
                          >
                            {reviewLoading[lp.id] ? "Reviewing..." : "Review this LP"}
                          </button>

                          {reviewError[lp.id] && (
                            <p className="mt-2 text-sm text-red-600">{reviewError[lp.id]}</p>
                          )}

                          {reviewData[lp.id] && (
                            <ReviewDisplay data={reviewData[lp.id]} />
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* Pagination */}
          {lpTotal > LP_LIMIT && (
            <div className="mt-6 flex items-center gap-3">
              <button
                type="button"
                onClick={() => {
                  if (session && selectedTeacher) {
                    const newOffset = Math.max(0, lpOffset - LP_LIMIT);
                    setLpOffset(newOffset);
                  }
                }}
                disabled={lpOffset === 0 || lpLoading}
                className="px-4 py-2 text-sm font-medium border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment-mid transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer bg-white"
              >
                Previous
              </button>
              <span className="text-sm text-dars-muted">
                Page {currentPage} of {totalPages}
              </span>
              <button
                type="button"
                onClick={() => {
                  if (session && selectedTeacher) {
                    const newOffset = lpOffset + LP_LIMIT;
                    setLpOffset(newOffset);
                  }
                }}
                disabled={lpOffset + LP_LIMIT >= lpTotal || lpLoading}
                className="px-4 py-2 text-sm font-medium border border-dars-rule-dark rounded-md text-dars-ink hover:bg-dars-parchment-mid transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer bg-white"
              >
                Next
              </button>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
