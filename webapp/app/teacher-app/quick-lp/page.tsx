/**
 * F4.14 — Quick LP.
 *
 * Form → POST /api/v1/quick-lp → display the new generation status in
 * a slide-over. The LP generation is async (60-120s); the slide-over
 * polls /refresh until terminal.
 */
"use client";

import { useState } from "react";

import { LPContentViewer } from "@/components/molecules/lp-content-viewer";
import { SlideOver } from "@/components/molecules/slide-over";
import { DarsApiError, quick } from "@/lib/dars-api";

const LP_TYPES_BY_SUBJECT: Record<string, string[]> = {
  Eng: ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
  Urdu: ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
  Maths: ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
  Science: ["revision"],
  GK: ["revision"],
};

export default function QuickLPPage() {
  const [curriculumCode, setCurriculumCode] = useState("DARS");
  const [grade, setGrade] = useState<number>(1);
  const [subject, setSubject] = useState<string>("Eng");
  const [lpType, setLpType] = useState<string>("reading");
  const [pageContent, setPageContent] = useState("");
  const [classStrength, setClassStrength] = useState<number>(30);
  const [bilingual, setBilingual] = useState(false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = await quick.lp({
        curriculum_code: curriculumCode,
        grade,
        subject,
        page_content: pageContent,
        lp_type: lpType,
        class_strength: classStrength,
        generate_bilingual: bilingual,
      });
      setResultId(res.id);
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
            Quick LP
          </h1>
          <p className="text-sm text-dars-muted mt-1">
            Generate a one-off lesson plan. Bypasses the cache — every
            submit fires a fresh upstream request.
          </p>
        </header>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
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
                onChange={(e) => {
                  const s = e.target.value;
                  setSubject(s);
                  setLpType(LP_TYPES_BY_SUBJECT[s]?.[0] ?? "revision");
                }}
                className="select"
              >
                {Object.keys(LP_TYPES_BY_SUBJECT).map((s) => (
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

          <Field label="Page content">
            <textarea
              value={pageContent}
              onChange={(e) => setPageContent(e.target.value)}
              rows={8}
              required
              placeholder="Paste the topic text the LP should be built from."
              className="w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-sm text-dars-ink font-mono"
            />
          </Field>

          <div className="flex flex-wrap items-center gap-4">
            <Field label="Class size">
              <input
                type="number"
                min={1}
                value={classStrength}
                onChange={(e) => setClassStrength(Number(e.target.value))}
                className="w-24 px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
              />
            </Field>
            <label className="flex items-center gap-2 text-sm text-dars-ink-soft mt-5">
              <input
                type="checkbox"
                checked={bilingual}
                onChange={(e) => setBilingual(e.target.checked)}
              />
              Generate bilingual
            </label>
          </div>

          {error ? <p className="text-sm text-dars-terra" role="alert">{error}</p> : null}

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={busy || !pageContent.trim()}
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
