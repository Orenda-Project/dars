/**
 * F5.9 — Curriculum browser.
 *
 * Tabs: SLOs / Books. Read-only. Filtered by grade + subject.
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  books as booksApi,
  curriculum as curriculumApi,
  DarsApiError,
  admin,
  type AdminMeResponse,
  type Book,
  type Grade,
  type SLO,
  type SubSLO,
  type Subject,
} from "@/lib/dars-api";

type Tab = "slos" | "books";

export default function CurriculumPage() {
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [tab, setTab] = useState<Tab>("slos");
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [gradeId, setGradeId] = useState<string>("");
  const [subjectId, setSubjectId] = useState<string>("");
  const [slos, setSlos] = useState<SLO[]>([]);
  const [subSlosBySlo, setSubSlosBySlo] = useState<Record<string, SubSLO[]>>({});
  const [books, setBooks] = useState<Book[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [m, { items: gs }, { items: ss }] = await Promise.all([
        admin.me(),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setMe(m);
      setGrades(gs);
      setSubjects(ss);
      if (!gradeId && gs[0]) setGradeId(gs[0].id);
      if (!subjectId && ss[0]) setSubjectId(ss[0].id);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [gradeId, subjectId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!me || !gradeId || !subjectId) return;
    let cancelled = false;
    (async () => {
      try {
        if (tab === "slos") {
          const { items } = await curriculumApi.getSLOs({
            curriculum_id: me.curriculum_id,
            grade_id: gradeId,
            subject_id: subjectId,
          });
          if (!cancelled) setSlos(items);
        } else {
          const { items } = await booksApi.getBooks({
            curriculum_id: me.curriculum_id,
            grade_id: gradeId,
            subject_id: subjectId,
          });
          if (!cancelled) setBooks(items);
        }
      } catch (err) {
        if (!cancelled) setError(formatErr(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tab, me, gradeId, subjectId]);

  async function toggleSlo(sloId: string) {
    if (subSlosBySlo[sloId]) {
      const next = { ...subSlosBySlo };
      delete next[sloId];
      setSubSlosBySlo(next);
      return;
    }
    try {
      const { items } = await curriculumApi.getSubSLOs(sloId);
      setSubSlosBySlo((prev) => ({ ...prev, [sloId]: items }));
    } catch (err) {
      setError(formatErr(err));
    }
  }

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        Curriculum
      </h1>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <select
          value={gradeId}
          onChange={(e) => setGradeId(e.target.value)}
          className="px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm"
        >
          {grades.map((g) => (
            <option key={g.id} value={g.id}>{g.display_name}</option>
          ))}
        </select>
        <select
          value={subjectId}
          onChange={(e) => setSubjectId(e.target.value)}
          className="px-2 py-1.5 rounded border border-dars-rule-light bg-white text-sm"
        >
          {subjects.map((s) => (
            <option key={s.id} value={s.id}>{s.code} — {s.display_name}</option>
          ))}
        </select>
        <span className="ml-auto text-xs text-dars-muted-light">
          Curriculum: <code className="font-mono">{me?.curriculum_code}</code>
        </span>
      </div>

      <nav className="border-b border-dars-rule-light mb-4 flex gap-1">
        {(["slos", "books"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={
              "px-3 py-2 text-sm border-b-2 -mb-px " +
              (tab === t
                ? "border-dars-terra text-dars-terra font-semibold"
                : "border-transparent text-dars-muted hover:text-dars-ink")
            }
          >
            {t === "slos" ? "SLOs" : "Books"}
          </button>
        ))}
      </nav>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      {tab === "slos" ? (
        <ul className="space-y-2">
          {slos.length === 0 ? (
            <li className="text-sm text-dars-muted">No SLOs for this combination.</li>
          ) : (
            slos.map((s) => (
              <li key={s.id} className="rounded border border-dars-rule-light bg-dars-parchment-mid">
                <button
                  type="button"
                  onClick={() => toggleSlo(s.id)}
                  className="w-full p-3 text-left flex items-start gap-2 hover:bg-dars-parchment-deep"
                >
                  <span className="font-mono text-xs text-dars-muted">{s.code}</span>
                  <span className="flex-1 text-sm text-dars-ink">{s.statement}</span>
                  <span className="text-[10px] text-dars-muted">
                    {subSlosBySlo[s.id] ? "▼" : "▶"}
                  </span>
                </button>
                {subSlosBySlo[s.id] ? (
                  <ul className="border-t border-dars-rule-light divide-y divide-dars-rule-light text-xs">
                    {subSlosBySlo[s.id].map((ss) => (
                      <li key={ss.id} className="px-3 py-1.5 flex gap-2">
                        <span className="font-mono text-dars-muted">{ss.code}</span>
                        <span className="text-dars-ink-soft">{ss.statement}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))
          )}
        </ul>
      ) : (
        <ul className="space-y-2">
          {books.length === 0 ? (
            <li className="text-sm text-dars-muted">No books for this combination.</li>
          ) : (
            books.map((b) => (
              <li key={b.id}>
                <Link
                  href={`/dashboard/curriculum/books/${b.id}`}
                  className="block rounded border border-dars-rule-light bg-dars-parchment-mid p-3 hover:bg-dars-parchment-deep"
                >
                  <p className="font-medium text-dars-ink">{b.title}</p>
                  <p className="text-[10px] font-mono text-dars-muted-light">{b.id.slice(0, 8)}…</p>
                </Link>
              </li>
            ))
          )}
        </ul>
      )}
    </div>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
