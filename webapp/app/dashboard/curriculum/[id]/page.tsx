"use client";

import React, { useEffect, useState } from "react";
import { BookLoader } from "@/components/atoms";
import { useParams } from "next/navigation";

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
  status: string;
}

interface CurriculumTopicDetail {
  id: string;
  sequence: number;
  title: string;
  lp_stubs: LpStub[];
}

interface CurriculumDetail {
  id: string;
  name: string;
  provider: string;
  grade: string;
  subject: string;
  academic_year: string;
  topics: CurriculumTopicDetail[];
}

interface MockLpCard {
  stubId: string;
  title: string;
  description: string;
}

function StubStatusBadge({ status }: { status: string }) {
  if (status === "generated") {
    return (
      <span className="inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-green-100 text-green-800">
        generated
      </span>
    );
  }
  return (
    <span className="inline-block text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded bg-dars-rule-light text-dars-muted">
      pending
    </span>
  );
}

export default function CurriculumDetailPage() {
  const params = useParams<{ id: string }>();
  const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

  const [session, setSession] = useState<Session | null>(null);
  const [curriculum, setCurriculum] = useState<CurriculumDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Per-topic expanded state
  const [expandedTopics, setExpandedTopics] = useState<Set<string>>(new Set());

  // Client-side status overrides for stubs
  const [generatedStubs, setGeneratedStubs] = useState<Set<string>>(new Set());
  // Mock LP cards shown inline below a stub
  const [mockCards, setMockCards] = useState<Record<string, MockLpCard>>({});

  useEffect(() => {
    const raw = localStorage.getItem("dars_session");
    if (!raw) {
      window.location.href = "/login";
      return;
    }
    setSession(JSON.parse(raw) as Session);
  }, []);

  useEffect(() => {
    if (!session || !params.id) return;
    fetchCurriculum(session.api_key, params.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session, params.id]);

  function fetchCurriculum(apiKey: string, id: string) {
    setLoading(true);
    setError(null);
    fetch(`${apiBase}/api/v1/curriculum/curriculums/${id}`, {
      headers: { "X-API-Key": apiKey },
    })
      .then(async (res) => {
        if (!res.ok) {
          if (res.status === 401) {
            localStorage.removeItem("dars_session");
            window.location.href = "/login";
            return;
          }
          if (res.status === 404) throw new Error("Curriculum not found.");
          throw new Error("Failed to fetch curriculum.");
        }
        const data = (await res.json()) as CurriculumDetail;
        setCurriculum(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "An unexpected error occurred.");
        setLoading(false);
      });
  }

  function toggleTopic(topicId: string) {
    setExpandedTopics((prev) => {
      const next = new Set(prev);
      if (next.has(topicId)) {
        next.delete(topicId);
      } else {
        next.add(topicId);
      }
      return next;
    });
  }

  function handleGenerateLP(topic: CurriculumTopicDetail, stub: LpStub) {
    // Client-side only — mark stub as generated and show a mock card
    setGeneratedStubs((prev) => new Set(prev).add(stub.id));

    const subSloStatement = "Students connect to the topic through meaningful context.";
    const card: MockLpCard = {
      stubId: stub.id,
      title: `Sample LP: ${topic.title} — ${stub.skill_type ?? "general"}`,
      description: `This lesson covers ${subSloStatement} using ${stub.cpa_phase ?? "concrete"} approach.`,
    };
    setMockCards((prev) => ({ ...prev, [stub.id]: card }));
  }

  if (loading) {
    return (
      <div className="p-8">
        <div className="flex justify-center items-center min-h-[110px]">
          <BookLoader />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8">
        <p className="text-sm text-red-600 border border-red-200 rounded-md px-3 py-2 bg-red-50">
          {error}
        </p>
        <a
          href="/dashboard/curriculum"
          className="mt-4 inline-block text-sm text-dars-terra hover:underline"
        >
          Back to Curriculum
        </a>
      </div>
    );
  }

  if (!curriculum) return null;

  return (
    <div className="p-8 max-w-5xl">
      {/* Breadcrumb */}
      <nav className="mb-6">
        <a
          href="/dashboard/curriculum"
          className="text-xs text-dars-muted hover:text-dars-ink transition-colors no-underline"
        >
          Curriculum
        </a>
        <span className="text-xs text-dars-muted mx-2">/</span>
        <span className="text-xs text-dars-ink font-medium">{curriculum.name}</span>
      </nav>

      {/* Curriculum meta */}
      <div className="mb-8 border border-dars-rule-light rounded-lg bg-dars-parchment p-5">
        <h1 className="text-xl font-serif font-bold text-dars-ink mb-1">{curriculum.name}</h1>
        <p className="text-sm text-dars-muted mb-4">{curriculum.provider}</p>
        <div className="flex flex-wrap gap-2">
          <span className="text-[11px] font-medium text-dars-muted bg-white border border-dars-rule-light px-2.5 py-1 rounded">
            {curriculum.grade}
          </span>
          <span className="text-[11px] font-medium text-dars-muted bg-white border border-dars-rule-light px-2.5 py-1 rounded">
            {curriculum.subject}
          </span>
          {curriculum.academic_year && (
            <span className="text-[11px] font-medium text-dars-muted bg-white border border-dars-rule-light px-2.5 py-1 rounded">
              {curriculum.academic_year}
            </span>
          )}
        </div>
      </div>

      {/* Topics table */}
      <section>
        <h2 className="text-lg font-serif font-semibold text-dars-ink mb-4">Topics</h2>

        {curriculum.topics.length === 0 && (
          <p className="text-sm text-dars-muted">No topics in this curriculum.</p>
        )}

        <div className="space-y-3">
          {curriculum.topics.map((topic) => {
            const isExpanded = expandedTopics.has(topic.id);
            return (
              <div
                key={topic.id}
                className="border border-dars-rule-light rounded-lg bg-dars-parchment overflow-hidden"
              >
                {/* Topic row */}
                <button
                  type="button"
                  onClick={() => toggleTopic(topic.id)}
                  className="w-full text-left px-5 py-4 flex items-center gap-4 hover:bg-dars-parchment-deep transition-colors cursor-pointer bg-transparent border-none"
                >
                  <span className="shrink-0 w-7 h-7 flex items-center justify-center rounded-full bg-dars-terra/10 text-xs font-semibold text-dars-terra">
                    {topic.sequence}
                  </span>
                  <span className="flex-1 text-sm font-semibold text-dars-ink">{topic.title}</span>
                  <span className="text-xs text-dars-muted shrink-0">
                    {topic.lp_stubs.length} LP stub{topic.lp_stubs.length !== 1 ? "s" : ""}
                  </span>
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

                {/* Expanded LP stubs */}
                {isExpanded && (
                  <div className="border-t border-dars-rule-light bg-white">
                    {topic.lp_stubs.length === 0 ? (
                      <p className="px-5 py-4 text-sm text-dars-muted">No LP stubs defined.</p>
                    ) : (
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b border-dars-rule-light bg-dars-parchment/50">
                            <th className="text-left px-5 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide w-12">
                              #
                            </th>
                            <th className="text-left px-3 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide">
                              Skill Type
                            </th>
                            <th className="text-left px-3 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide">
                              CPA Phase
                            </th>
                            <th className="text-left px-3 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide">
                              Bloom&apos;s Level
                            </th>
                            <th className="text-left px-3 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide">
                              Status
                            </th>
                            <th className="px-5 py-2.5 w-36"></th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-dars-rule-light">
                          {topic.lp_stubs.map((stub) => {
                            const isGenerated = generatedStubs.has(stub.id);
                            const card = mockCards[stub.id];
                            return (
                              <React.Fragment key={stub.id}>
                                <tr className="hover:bg-dars-parchment/40 transition-colors">
                                  <td className="px-5 py-3 text-xs text-dars-muted font-mono">
                                    {stub.sequence}
                                  </td>
                                  <td className="px-3 py-3 text-sm text-dars-ink capitalize">
                                    {stub.skill_type ?? "—"}
                                  </td>
                                  <td className="px-3 py-3 text-sm text-dars-ink capitalize">
                                    {stub.cpa_phase ?? "—"}
                                  </td>
                                  <td className="px-3 py-3 text-sm text-dars-ink capitalize">
                                    {stub.blooms_level ?? "—"}
                                  </td>
                                  <td className="px-3 py-3">
                                    <StubStatusBadge
                                      status={isGenerated ? "generated" : stub.status}
                                    />
                                  </td>
                                  <td className="px-5 py-3 text-right">
                                    <button
                                      type="button"
                                      onClick={() => handleGenerateLP(topic, stub)}
                                      disabled={isGenerated}
                                      className="px-3 py-1.5 bg-dars-terra text-white text-xs font-semibold rounded-md hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                                    >
                                      {isGenerated ? "Generated" : "Generate LP"}
                                    </button>
                                  </td>
                                </tr>
                                {card && (
                                  <tr key={`${stub.id}-card`}>
                                    <td colSpan={6} className="px-5 pb-4 pt-0">
                                      <div className="border border-green-200 rounded-md bg-green-50 p-4">
                                        <p className="text-sm font-semibold text-green-900 mb-1">
                                          {card.title}
                                        </p>
                                        <p className="text-sm text-green-800">{card.description}</p>
                                      </div>
                                    </td>
                                  </tr>
                                )}
                              </React.Fragment>
                            );
                          })}
                        </tbody>
                      </table>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
