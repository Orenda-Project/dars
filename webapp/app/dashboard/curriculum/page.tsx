"use client";

import { useCallback, useEffect, useState } from "react";
import { BookLoader } from "@/components/atoms";

interface Session {
  api_key: string;
  client_id: string;
  name: string;
  email: string;
}

interface LpStub {
  id: string;
  sequence: number;
  skill_type: string | null;
  cpa_phase: string | null;
  blooms_level: string | null;
  planned_date: string | null;
  lesson_plan_id: string | null;
}

interface CurriculumTopic {
  id: string;
  sequence: number;
  topic_id: string;
  topic_title: string;
  topic_text: string | null;
  planned_date: string | null;
  lp_stubs: LpStub[];
}

interface CurriculumDetail {
  id: string;
  name: string;
  book_id: number;
  book_title: string;
  provider_name: string;
  is_active: boolean;
  created_at: string;
  topics: CurriculumTopic[];
}

interface CurriculumListItem {
  id: string;
  name: string;
  book_id: number;
  book_title: string;
  provider_name: string;
  is_active: boolean;
}

interface LessonPlan {
  id: string;
  grade: string;
  subject: string;
  topic: string | null;
  content: string | null;
  content_bilingual: string | null;
  status: string;
  tags: string[];
  metadata: Record<string, unknown>;
}

// Derive topic completion status
function topicStatus(topic: CurriculumTopic): "all" | "partial" | "none" {
  const stubs = topic.lp_stubs;
  if (stubs.length === 0) return "none";
  const filled = stubs.filter((s) => s.lesson_plan_id !== null).length;
  if (filled === stubs.length) return "all";
  if (filled === 0) return "none";
  return "partial";
}

function StatusDot({ status }: { status: "all" | "partial" | "none" }) {
  const color =
    status === "all"
      ? "bg-green-500"
      : status === "partial"
        ? "bg-amber-400"
        : "bg-dars-muted/40";
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${color}`} />;
}

function capitalize(s: string | null | undefined): string {
  if (!s) return "";
  return s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
}

function StubCard({
  stub,
  apiBase,
  apiKey,
}: {
  stub: LpStub;
  apiBase: string;
  apiKey: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const [lp, setLp] = useState<LessonPlan | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const label =
    stub.skill_type
      ? `${capitalize(stub.skill_type)}${stub.cpa_phase ? " · " + stub.cpa_phase.toUpperCase() : ""}${stub.blooms_level ? " · " + capitalize(stub.blooms_level) : ""}`
      : "Revision";

  function handleToggle() {
    if (!stub.lesson_plan_id) return;
    if (!expanded && !lp && !loading) {
      setLoading(true);
      setError(null);
      fetch(`${apiBase}/api/v1/lesson-plans/${stub.lesson_plan_id}`, {
        headers: { "X-API-Key": apiKey },
      })
        .then(async (res) => {
          if (!res.ok) throw new Error("Failed to load lesson plan.");
          const data = (await res.json()) as LessonPlan;
          setLp(data);
          setLoading(false);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Error loading LP.");
          setLoading(false);
        });
    }
    setExpanded((v) => !v);
  }

  const hasLp = stub.lesson_plan_id !== null;

  return (
    <div className="border border-dars-rule-light rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={handleToggle}
        disabled={!hasLp}
        className={`w-full text-left px-4 py-3 flex items-center justify-between gap-3 bg-dars-parchment transition-colors border-none ${
          hasLp ? "cursor-pointer hover:bg-dars-parchment/70" : "cursor-default"
        }`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-xs font-semibold text-dars-muted shrink-0">#{stub.sequence}</span>
          <span className="text-sm font-medium text-dars-ink truncate">{label}</span>
          {stub.planned_date && (
            <span className="text-xs text-dars-muted shrink-0 hidden sm:inline">
              {new Date(stub.planned_date).toLocaleDateString("en-PK", {
                day: "numeric",
                month: "short",
              })}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {hasLp ? (
            <span className="inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-green-100 text-green-800">
              Ready
            </span>
          ) : (
            <span className="inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-dars-rule-light text-dars-muted">
              Pending
            </span>
          )}
          {hasLp && (
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className={`h-3.5 w-3.5 text-dars-muted transition-transform ${expanded ? "rotate-90" : ""}`}
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <polyline points="9 18 15 12 9 6" />
            </svg>
          )}
        </div>
      </button>

      {expanded && hasLp && (
        <div className="border-t border-dars-rule-light bg-white">
          {loading && (
            <div className="flex justify-center items-center py-8">
              <BookLoader />
            </div>
          )}
          {error && (
            <p className="px-4 py-4 text-sm text-red-600">{error}</p>
          )}
          {lp && (
            <div
              className="px-5 py-4 prose prose-sm max-w-none overflow-y-auto"
              style={{ maxHeight: "400px" }}
              dangerouslySetInnerHTML={{ __html: lp.content ?? "<p>No content available.</p>" }}
            />
          )}
        </div>
      )}
    </div>
  );
}

export default function CurriculumPage() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const [session, setSession] = useState<Session | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [noAssignment, setNoAssignment] = useState(false);
  const [selectedTopicId, setSelectedTopicId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"topics" | "schedule">("topics");

  const fetchCurriculum = useCallback(
    (apiKey: string) => {
      setLoading(true);
      setError(null);
      setNoAssignment(false);

      fetch(`${apiBase}/api/v1/curriculums`, {
        headers: { "X-API-Key": apiKey },
      })
        .then(async (res) => {
          if (!res.ok) {
            if (res.status === 401) {
              localStorage.removeItem("dars_session");
              window.location.href = "/login";
              return;
            }
            throw new Error("Failed to load curricula.");
          }
          const list = (await res.json()) as CurriculumListItem[];
          const active = list.find((c) => c.is_active) ?? list[0] ?? null;
          if (!active) {
            setNoAssignment(true);
            setLoading(false);
            return;
          }

          return fetch(`${apiBase}/api/v1/curriculums/${active.id}`, {
            headers: { "X-API-Key": apiKey },
          });
        })
        .then(async (res) => {
          if (!res) return;
          if (!res.ok) throw new Error("Failed to load curriculum detail.");
          const detail = (await res.json()) as CurriculumDetail;
          setCurriculum(detail);
          if (detail.topics.length > 0) {
            setSelectedTopicId(detail.topics[0].id);
          }
          setLoading(false);
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "An unexpected error occurred.");
          setLoading(false);
        });
    },
    [apiBase]
  );

  useEffect(() => {
    const raw = localStorage.getItem("dars_session");
    if (!raw) {
      window.location.href = "/login";
      return;
    }
    const s = JSON.parse(raw) as Session;
    setSession(s);
    fetchCurriculum(s.api_key);
  }, [fetchCurriculum]);

  const selectedTopic = curriculum?.topics.find((t) => t.id === selectedTopicId) ?? null;

  // Derive flat stub list for Schedule tab
  interface ScheduleRow {
    stub: LpStub;
    topic: CurriculumTopic;
  }
  const scheduleRows: ScheduleRow[] = curriculum
    ? curriculum.topics.flatMap((topic) =>
        topic.lp_stubs.map((stub) => ({ stub, topic }))
      ).sort((a, b) => {
        if (!a.stub.planned_date && !b.stub.planned_date) return 0;
        if (!a.stub.planned_date) return 1;
        if (!b.stub.planned_date) return -1;
        return a.stub.planned_date.localeCompare(b.stub.planned_date);
      })
    : [];

  function formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-PK", { day: "numeric", month: "short" });
  }

  return (
    <div className="h-full flex flex-col">
      {/* Page header */}
      <div className="px-8 py-5 border-b border-dars-rule-light shrink-0">
        <h1 className="text-xl font-serif font-bold text-dars-ink">My Curriculum</h1>
        {session && (
          <p className="text-sm text-dars-muted mt-0.5">
            {session.name} &middot; {session.email}
          </p>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex-1 flex items-center justify-center">
          <BookLoader />
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="flex-1 flex items-center justify-center px-8">
          <p className="text-sm text-red-600 border border-red-200 rounded-md px-4 py-3 bg-red-50 max-w-md text-center">
            {error}
          </p>
        </div>
      )}

      {/* No assignment */}
      {!loading && noAssignment && (
        <div className="flex-1 flex items-center justify-center px-8">
          <div className="text-center max-w-sm">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-10 w-10 text-dars-muted/40 mx-auto mb-3"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
              <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
            </svg>
            <p className="text-sm text-dars-muted">
              No curriculum assigned. Contact your admin.
            </p>
          </div>
        </div>
      )}

      {/* Two-panel layout */}
      {!loading && !error && curriculum && (
        <div className="flex-1 flex overflow-hidden min-h-0">
          {/* Left panel — topic tree */}
          <div
            className="shrink-0 border-r border-dars-rule-light flex flex-col overflow-hidden bg-dars-parchment"
            style={{ width: "280px" }}
          >
            {/* Panel header */}
            <div className="px-4 py-3 border-b border-dars-rule-light">
              <p className="text-xs font-semibold text-dars-ink leading-snug truncate">
                {curriculum.name}
              </p>
              <p className="text-xs text-dars-muted truncate mt-0.5">{curriculum.book_title}</p>
            </div>

            {/* Topic list */}
            <ul className="flex-1 overflow-y-auto divide-y divide-dars-rule-light">
              {curriculum.topics.length === 0 && (
                <li className="px-4 py-4 text-sm text-dars-muted">No topics in this curriculum.</li>
              )}
              {curriculum.topics.map((topic) => {
                const isSelected = topic.id === selectedTopicId;
                const status = topicStatus(topic);
                return (
                  <li key={topic.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedTopicId(topic.id)}
                      className={`w-full text-left px-4 py-3 flex items-start gap-2.5 transition-colors border-none cursor-pointer ${
                        isSelected
                          ? "bg-dars-terra/10 border-l-2 border-l-dars-terra"
                          : "bg-transparent hover:bg-white/60"
                      }`}
                    >
                      <StatusDot status={status} />
                      <div className="min-w-0 flex-1">
                        <span
                          className={`text-xs font-semibold mr-1.5 ${
                            isSelected ? "text-dars-terra" : "text-dars-muted"
                          }`}
                        >
                          {topic.sequence}.
                        </span>
                        <span
                          className={`text-sm leading-snug ${
                            isSelected
                              ? "text-dars-terra font-medium"
                              : "text-dars-ink"
                          }`}
                        >
                          {topic.topic_title}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Right panel — tab switcher + content */}
          <div className="flex-1 flex flex-col overflow-hidden bg-white">
            {/* Tab switcher */}
            <div className="px-8 py-3 border-b border-dars-rule-light shrink-0 flex gap-2">
              <button
                type="button"
                onClick={() => setActiveTab("topics")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors border-none cursor-pointer ${
                  activeTab === "topics"
                    ? "bg-dars-terra text-white"
                    : "text-dars-muted hover:text-dars-ink"
                }`}
              >
                Topics
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("schedule")}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors border-none cursor-pointer ${
                  activeTab === "schedule"
                    ? "bg-dars-terra text-white"
                    : "text-dars-muted hover:text-dars-ink"
                }`}
              >
                Schedule
              </button>
            </div>

            {/* Topics tab */}
            {activeTab === "topics" && (
              <div className="flex-1 overflow-y-auto">
                {!selectedTopic ? (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-sm text-dars-muted">Select a topic from the list.</p>
                  </div>
                ) : (
                  <div className="px-8 py-6 max-w-3xl">
                    {/* Topic header */}
                    <div className="mb-6">
                      <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest mb-1">
                        Topic {selectedTopic.sequence}
                      </p>
                      <h2 className="text-xl font-serif font-bold text-dars-ink">
                        {selectedTopic.topic_title}
                      </h2>
                      {selectedTopic.planned_date && (
                        <p className="text-xs text-dars-muted mt-1">
                          Planned:{" "}
                          {new Date(selectedTopic.planned_date).toLocaleDateString("en-PK", {
                            day: "numeric",
                            month: "long",
                            year: "numeric",
                          })}
                        </p>
                      )}
                    </div>

                    {/* Topic text */}
                    {selectedTopic.topic_text && (
                      <div className="mb-8 border border-dars-rule-light rounded-lg bg-dars-parchment p-5">
                        <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest mb-3">
                          Textbook Passage
                        </p>
                        <div className="prose prose-sm max-w-none text-dars-ink leading-relaxed font-serif text-sm whitespace-pre-wrap">
                          {selectedTopic.topic_text}
                        </div>
                      </div>
                    )}

                    {/* LP stubs */}
                    <div>
                      <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest mb-3">
                        Lesson Plans
                      </p>
                      {selectedTopic.lp_stubs.length === 0 ? (
                        <p className="text-sm text-dars-muted">
                          No lesson plan stubs for this topic.
                        </p>
                      ) : (
                        <div className="space-y-3">
                          {selectedTopic.lp_stubs.map((stub) =>
                            session ? (
                              <StubCard
                                key={stub.id}
                                stub={stub}
                                apiBase={apiBase}
                                apiKey={session.api_key}
                              />
                            ) : null
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Schedule tab */}
            {activeTab === "schedule" && (
              <div className="flex-1 overflow-y-auto">
                {scheduleRows.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-sm text-dars-muted">No lesson plan stubs scheduled.</p>
                  </div>
                ) : (
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr className="bg-dars-parchment border-b border-dars-rule-light">
                        <th className="text-left px-6 py-3 text-xs font-semibold text-dars-muted uppercase tracking-widest w-24">Date</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-widest">Topic</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-widest">Lesson</th>
                        <th className="text-left px-4 py-3 text-xs font-semibold text-dars-muted uppercase tracking-widest w-24">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(() => {
                        let lastDate: string | null = null;
                        return scheduleRows.map((row) => {
                          const dateKey = row.stub.planned_date ?? null;
                          const showDate = dateKey !== lastDate;
                          lastDate = dateKey;
                          const lessonLabel = row.stub.skill_type
                            ? `${capitalize(row.stub.skill_type)}${row.stub.cpa_phase ? " · " + row.stub.cpa_phase.toUpperCase() : ""}${row.stub.blooms_level ? " · " + capitalize(row.stub.blooms_level) : ""}`
                            : "Revision";
                          return (
                            <tr
                              key={row.stub.id}
                              onClick={() => {
                                setSelectedTopicId(row.topic.id);
                                setActiveTab("topics");
                              }}
                              className="border-b border-dars-rule-light hover:bg-dars-parchment/60 cursor-pointer transition-colors"
                            >
                              <td className="px-6 py-3 text-dars-ink font-medium whitespace-nowrap">
                                {showDate
                                  ? dateKey
                                    ? formatDate(dateKey)
                                    : <span className="text-dars-muted">—</span>
                                  : ""}
                              </td>
                              <td className="px-4 py-3 text-dars-ink">{row.topic.topic_title}</td>
                              <td className="px-4 py-3 text-dars-muted">{lessonLabel}</td>
                              <td className="px-4 py-3">
                                {row.stub.lesson_plan_id ? (
                                  <span className="inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-green-100 text-green-800">
                                    Ready
                                  </span>
                                ) : (
                                  <span className="text-dars-muted">—</span>
                                )}
                              </td>
                            </tr>
                          );
                        });
                      })()}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
