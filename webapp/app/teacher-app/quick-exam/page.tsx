/**
 * F4.14 — Quick Exam.
 *
 * Single-screen form. Defaults match the seed (English FA: MCQs +
 * True/False + Fill in the Blanks). Generates a fresh exam off-cache;
 * displays status in a slide-over.
 *
 * Curriculum is read from the calling org (admin.me().curriculum_code)
 * — never asked. User picks grade + subject + page range + question
 * config.
 */
"use client";

import { useEffect, useState } from "react";

import { SlideOver } from "@/components/molecules/slide-over";
import {
  DarsApiError,
  admin,
  curriculum as curriculumApi,
  generations,
  quick,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

function buildPageRange(startPage: number, endPage: number): string {
  if (startPage === endPage) return String(startPage);
  return `${startPage}-${endPage}`;
}

export default function QuickExamPage() {
  const [curriculumCode, setCurriculumCode] = useState<string>("");
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [grade, setGrade] = useState<number>(1);
  const [subject, setSubject] = useState<string>("Eng");
  const [startPage, setStartPage] = useState<number>(1);
  const [endPage, setEndPage] = useState<number>(1);

  // Default config = English G1 FA
  const [mcqs, setMcqs] = useState<number>(5);
  const [tf, setTf] = useState<number>(3);
  const [fib, setFib] = useState<number>(2);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const [resultStatus, setResultStatus] = useState<string | null>(null);

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
      const res = await quick.exam({
        grade,
        subject,
        page_ranges: buildPageRange(startPage, endPage),
        question_types: ["unseen"],
        unseen_categories: ["objective"],
        unseen_objective_types: ["MCQs", "True/False", "Fill in the Blanks"],
        unseen_objective_counts: {
          MCQs: mcqs,
          "True/False": tf,
          "Fill in the Blanks": fib,
        },
      });
      setResultId(res.id);
      setResultStatus(res.status);
      pollExam(res.id, (s) => setResultStatus(s));
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  const subjectCodes = subjects.length > 0
    ? subjects.map((s) => s.code)
    : ["Eng", "Urdu", "Maths"];

  return (
    <>
      <div className="max-w-2xl space-y-5">
        <header>
          <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
            Quick Exam
          </h1>
          <p className="text-sm text-dars-muted mt-1">
            Generate a one-off exam. Defaults reproduce the seed's formative
            assessment configuration.
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
          <div className="grid grid-cols-2 sm:grid-cols-2 gap-3">
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
                onChange={(e) => setSubject(e.target.value)}
                className="select"
              >
                {subjectCodes.map((s) => (
                  <option key={s} value={s}>
                    {s}
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
              UG_EG fetches book content from its DB. For a single page set
              start = end.
            </p>
          </fieldset>

          <fieldset className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
            <legend className="text-xs font-semibold text-dars-ink-soft px-1">
              Question counts (objective only)
            </legend>
            <div className="grid grid-cols-3 gap-3 mt-2">
              <CountField label="MCQs" value={mcqs} onChange={setMcqs} />
              <CountField label="True / False" value={tf} onChange={setTf} />
              <CountField label="Fill in the Blanks" value={fib} onChange={setFib} />
            </div>
          </fieldset>

          {error ? <p className="text-sm text-dars-terra" role="alert">{error}</p> : null}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={busy || !curriculumCode}
              className="px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Submitting…" : "Generate Exam →"}
            </button>
          </div>
        </form>
      </div>

      <SlideOver
        open={resultId !== null}
        onClose={() => {
          setResultId(null);
          setResultStatus(null);
        }}
        title="Quick Exam"
        subtitle={resultId ? `id: ${resultId.slice(0, 8)}…  ·  status: ${resultStatus}` : undefined}
      >
        {resultId ? <ExamStatusPane status={resultStatus} id={resultId} /> : null}
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

function pollExam(id: string, onChange: (s: string) => void) {
  let count = 0;
  const tick = async () => {
    if (count > 80) return;
    count += 1;
    try {
      const r = await generations.refreshExam(id);
      onChange(r.status);
      if (r.status === "READY" || r.status === "ERROR") return;
    } catch {
      // ignore; user can close
    }
    setTimeout(tick, 3000);
  };
  setTimeout(tick, 3000);
}

function ExamStatusPane({ status, id }: { status: string | null; id: string }) {
  if (status === "READY") {
    return (
      <div className="rounded-md border border-emerald-300 bg-emerald-50 p-4 text-sm text-dars-ink">
        <p className="font-semibold">Exam ready.</p>
        <p className="text-xs text-dars-muted mt-1 break-all">
          Row id: <code className="font-mono">{id}</code>.
        </p>
        <p className="text-xs text-dars-muted-light mt-2">
          A read endpoint for one-off exam content lands in Phase 5.
        </p>
      </div>
    );
  }
  if (status === "ERROR") {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm">
        <p className="font-semibold text-dars-ink">Generation failed.</p>
      </div>
    );
  }
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-muted flex items-center gap-3">
      <span className="h-2 w-2 rounded-full bg-dars-terra animate-pulse" />
      Generating (status={status ?? "PENDING"})…
    </div>
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

function CountField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (n: number) => void;
}) {
  return (
    <label className="flex flex-col">
      <span className="text-xs text-dars-ink-soft mb-1">{label}</span>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
      />
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
