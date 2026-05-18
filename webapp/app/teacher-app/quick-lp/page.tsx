/**
 * F4.14 — Quick LP.
 *
 * Form → POST /api/v1/quick-lp → display the new generation status in
 * a slide-over. The LP generation is async (60-120s); the slide-over
 * polls /refresh until terminal.
 *
 * Curriculum is read from the calling org (admin.me().curriculum_code)
 * — never asked. User picks grade + subject + lp_type + page range.
 * Class size is not exposed; LP Assistant's default is used.
 */
"use client";

import { useEffect, useState } from "react";

import { LPContentViewer } from "@/components/molecules/lp-content-viewer";
import { SlideOver } from "@/components/molecules/slide-over";
import {
  DarsApiError,
  admin,
  curriculum as curriculumApi,
  quick,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

const LP_TYPES_BY_SUBJECT: Record<string, string[]> = {
  Eng: ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
  Urdu: ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
  Maths: ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
  Science: ["revision"],
  GK: ["revision"],
};

function buildPageRange(startPage: number, endPage: number): string {
  if (startPage === endPage) return String(startPage);
  return `${startPage}-${endPage}`;
}

export default function QuickLPPage() {
  const [curriculumCode, setCurriculumCode] = useState<string>("");
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [grade, setGrade] = useState<number>(1);
  const [subject, setSubject] = useState<string>("Eng");
  const [lpType, setLpType] = useState<string>("reading");
  const [startPage, setStartPage] = useState<number>(1);
  const [endPage, setEndPage] = useState<number>(1);
  const [bilingual, setBilingual] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);

  // Bootstrap: read org curriculum + the available grades/subjects.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [me, { items: gs }, { items: ss }] = await Promise.all([
          admin.me(),
          curriculumApi.getGrades(),
          curriculumApi.getSubjects(),
        ]);
        if (cancelled) return;
        setCurriculumCode(me.curriculum_code);
        setGrades(gs);
        setSubjects(ss);
        if (gs[0]) setGrade(gs[0].code);
      } catch (err) {
        if (cancelled) return;
        setLoadError(formatErr(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (endPage < startPage) {
      setError("End page must be ≥ start page.");
      return;
    }
    setBusy(true);
    try {
      const res = await quick.lp({
        grade,
        subject,
        page_number: buildPageRange(startPage, endPage),
        lp_type: lpType,
        generate_bilingual: bilingual,
      });
      setResultId(res.id);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  const subjectCodes = subjects.length > 0
    ? subjects.map((s) => s.code).filter((c) => c in LP_TYPES_BY_SUBJECT)
    : Object.keys(LP_TYPES_BY_SUBJECT);

  return (
    <>
      <div className="max-w-2xl space-y-5">
        <header>
          <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
            Quick LP
          </h1>
          <p className="text-sm text-dars-muted mt-1">
            Generate a one-off lesson plan. Bypasses the cache — every
            submit fires a fresh upstream request.
          </p>
          {curriculumCode ? (
            <p className="text-xs text-dars-muted-light mt-1">
              Curriculum: <code className="font-mono">{curriculumCode}</code>
            </p>
          ) : null}
        </header>

        {loadError ? (
          <p className="text-sm text-dars-terra" role="alert">{loadError}</p>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <Field label="Grade">
              <select
                value={grade}
                onChange={(e) => setGrade(Number(e.target.value))}
                className="select"
              >
                {(grades.length > 0
                  ? grades.map((g) => ({ code: g.code, label: g.display_name }))
                  : [1, 2, 3, 4, 5].map((g) => ({ code: g, label: `Grade ${g}` }))
                ).map((g) => (
                  <option key={g.code} value={g.code}>
                    {g.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Subject">
              <select
                value={subject}
                onChange={(e) => {
                  const s = e.target.value;
                  setSubject(s);
                  setLpType(LP_TYPES_BY_SUBJECT[s]?.[0] ?? "revision");
                }}
                className="select"
              >
                {subjectCodes.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="LP type">
              <select
                value={lpType}
                onChange={(e) => setLpType(e.target.value)}
                className="select"
              >
                {(LP_TYPES_BY_SUBJECT[subject] ?? []).map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <fieldset className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
            <legend className="text-xs font-semibold text-dars-ink-soft px-1">
              Pages
            </legend>
            <div className="grid grid-cols-2 gap-3 mt-2">
              <Field label="Start page">
                <input
                  type="number"
                  min={1}
                  value={startPage}
                  onChange={(e) => setStartPage(Number(e.target.value))}
                  className="px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
                />
              </Field>
              <Field label="End page">
                <input
                  type="number"
                  min={startPage}
                  value={endPage}
                  onChange={(e) => setEndPage(Number(e.target.value))}
                  className="px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
                />
              </Field>
            </div>
            <p className="text-[11px] text-dars-muted mt-2">
              LP Assistant fetches the page content from the book DB. For a
              single page, set start = end.
            </p>
          </fieldset>

          <label className="flex items-center gap-2 text-sm text-dars-ink-soft">
            <input
              type="checkbox"
              checked={bilingual}
              onChange={(e) => setBilingual(e.target.checked)}
            />
            Generate bilingual
          </label>

          {error ? <p className="text-sm text-dars-terra" role="alert">{error}</p> : null}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={busy || !curriculumCode}
              className="px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Submitting…" : "Generate LP →"}
            </button>
          </div>
        </form>
      </div>

      <SlideOver
        open={resultId !== null}
        onClose={() => setResultId(null)}
        title="Quick LP"
        subtitle={resultId ? `id: ${resultId.slice(0, 8)}…` : undefined}
      >
        {resultId ? <LPContentViewer generatedLPId={resultId} /> : null}
      </SlideOver>

      <style jsx>{`
        .select {
          padding: 0.5rem 0.75rem;
          border-radius: 0.375rem;
          border: 1px solid var(--color-dars-rule-light);
          background: white;
          font-size: 0.875rem;
          color: var(--color-dars-ink);
        }
      `}</style>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col">
      <span className="text-xs font-medium text-dars-ink-soft mb-1">{label}</span>
      {children}
    </label>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
