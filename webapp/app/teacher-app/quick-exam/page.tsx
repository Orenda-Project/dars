/**
 * F4.14 — Quick Exam.
 *
 * Single-screen form. Defaults match the seed (English FA: MCQs +
 * True/False + Fill in the Blanks). Generates a fresh exam off-cache;
 * displays status in a slide-over.
 */
"use client";

import { useState } from "react";

import { SlideOver } from "@/components/molecules/slide-over";
import { DarsApiError, generations, quick } from "@/lib/dars-api";

export default function QuickExamPage() {
  const [curriculumCode, setCurriculumCode] = useState("DARS");
  const [grade, setGrade] = useState<number>(1);
  const [subject, setSubject] = useState<string>("Eng");
  const [pageContent, setPageContent] = useState("");

  // Default config = English G1 FA
  const [mcqs, setMcqs] = useState<number>(5);
  const [tf, setTf] = useState<number>(3);
  const [fib, setFib] = useState<number>(2);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const [resultStatus, setResultStatus] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await quick.exam({
        curriculum_code: curriculumCode,
        grade,
        subject,
        page_content: pageContent,
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

      // Light poll loop while the user has the panel open.
      pollExam(res.id, (s) => setResultStatus(s));
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed",
      );
    } finally {
      setBusy(false);
    }
  }

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
        </header>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            <Field label="Curriculum">
              <select
                value={curriculumCode}
                onChange={(e) => setCurriculumCode(e.target.value)}
                className="select"
              >
                <option value="DARS">DARS</option>
                <option value="NCP">NCP</option>
                <option value="SNC">SNC</option>
              </select>
            </Field>
            <Field label="Grade">
              <select
                value={grade}
                onChange={(e) => setGrade(Number(e.target.value))}
                className="select"
              >
                {[1, 2, 3, 4, 5].map((g) => (
                  <option key={g} value={g}>
                    {g}
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
                {["Eng", "Urdu", "Maths"].map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          <Field label="Page content">
            <textarea
              value={pageContent}
              onChange={(e) => setPageContent(e.target.value)}
              rows={8}
              required
              placeholder="Paste the source text the exam should cover."
              className="w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-sm font-mono"
            />
          </Field>

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
              disabled={busy || !pageContent.trim()}
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
