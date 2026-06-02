/**
 * F4.12 — Mid-year onboarding wizard template.
 *
 * Two steps:
 *   1. Pick chapter + day-within-chapter
 *   2. Confirm → submit
 *
 * Page owns submission to POST /csts/{id}/onboard.
 */
"use client";

import { useState } from "react";

export interface OnboardingChapterOption {
  position: number;       // syllabus chapter.position (1..N)
  title: string;          // book chapter title
  teaching_days: number | null;  // derived chapter length in teaching days; null when no date range
}

interface OnboardingTemplateProps {
  className: string;
  chapters: OnboardingChapterOption[];
  onSubmit: (payload: { chapter_position: number; chapter_day: number }) => Promise<void>;
  loading: boolean;
  error: string | null;
}

export function OnboardingTemplate(props: OnboardingTemplateProps) {
  const { className, chapters, onSubmit, loading, error } = props;
  const [step, setStep] = useState<1 | 2>(1);
  const [chapterPosition, setChapterPosition] = useState<number | "">("");
  const [chapterDay, setChapterDay] = useState<number | "">("");
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const selectedChapter = chapters.find((c) => c.position === chapterPosition);

  if (loading) {
    return <p className="text-sm text-dars-muted">Loading syllabus breakdown…</p>;
  }
  if (error) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
        <p className="text-sm font-semibold text-dars-ink">Couldn’t load class</p>
        <p className="text-xs text-dars-muted mt-1">{error}</p>
      </div>
    );
  }
  if (chapters.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No syllabus breakdown yet</p>
        <p className="text-xs text-dars-muted mt-1">
          This class hasn't had a syllabus breakdown published; nothing to onboard against.
        </p>
      </div>
    );
  }

  async function handleSubmit() {
    if (chapterPosition === "" || chapterDay === "") return;
    setBusy(true);
    setSubmitError(null);
    try {
      await onSubmit({
        chapter_position: Number(chapterPosition),
        chapter_day: Number(chapterDay),
      });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Failed to submit");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-1">
        Where are you in {className}?
      </h1>
      <p className="text-sm text-dars-muted mb-6">
        Set your starting point so the calendar and SLO coverage start at the
        right place.
      </p>

      <ol className="flex items-center gap-2 text-xs mb-6">
        <li
          className={
            "px-2.5 py-1 rounded-full font-semibold " +
            (step === 1
              ? "bg-dars-terra text-dars-parchment"
              : "bg-dars-parchment-deep text-dars-muted")
          }
        >
          1. Pick position
        </li>
        <span className="text-dars-rule-light">›</span>
        <li
          className={
            "px-2.5 py-1 rounded-full font-semibold " +
            (step === 2
              ? "bg-dars-terra text-dars-parchment"
              : "bg-dars-parchment-deep text-dars-muted")
          }
        >
          2. Confirm
        </li>
      </ol>

      {step === 1 ? (
        <div className="space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-dars-ink-soft">Chapter</span>
            <select
              value={chapterPosition}
              onChange={(e) =>
                setChapterPosition(e.target.value === "" ? "" : Number(e.target.value))
              }
              className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-dars-ink text-sm focus:outline-none focus:ring-2 focus:ring-dars-terra"
            >
              <option value="">Select a chapter…</option>
              {chapters.map((c) => (
                <option key={c.position} value={c.position}>
                  Ch {c.position}: {c.title}
                  {c.teaching_days != null ? ` (${c.teaching_days} days)` : ""}
                </option>
              ))}
            </select>
          </label>

          <label className="block">
            <span className="text-sm font-medium text-dars-ink-soft">
              Day within chapter
            </span>
            <input
              type="number"
              min={1}
              max={selectedChapter?.teaching_days ?? undefined}
              value={chapterDay}
              onChange={(e) =>
                setChapterDay(e.target.value === "" ? "" : Number(e.target.value))
              }
              placeholder="e.g. 3"
              className="mt-1 w-full px-3 py-2 rounded-md border border-dars-rule-light bg-white text-dars-ink text-sm focus:outline-none focus:ring-2 focus:ring-dars-terra"
            />
            {selectedChapter && selectedChapter.teaching_days != null ? (
              <span className="text-xs text-dars-muted-light mt-1 block">
                This chapter is {selectedChapter.teaching_days} teaching days
                long. Day 1 = first day of the chapter.
              </span>
            ) : null}
          </label>

          <div className="flex justify-end">
            <button
              type="button"
              disabled={chapterPosition === "" || chapterDay === ""}
              onClick={() => setStep(2)}
              className="px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
            <p className="text-sm text-dars-ink">
              You'll start at{" "}
              <strong className="font-semibold">
                Chapter {chapterPosition} ({selectedChapter?.title})
              </strong>
              , Day {chapterDay}.
            </p>
            <p className="text-xs text-dars-muted mt-2">
              Slots before this position will be marked as <em>unknown</em> in
              your SLO coverage — they happened before you joined.
            </p>
          </div>

          {submitError ? (
            <p className="text-sm text-dars-terra" role="alert">
              {submitError}
            </p>
          ) : null}

          <div className="flex justify-between">
            <button
              type="button"
              onClick={() => setStep(1)}
              className="px-4 py-2 rounded-md border border-dars-rule-light text-sm text-dars-ink hover:bg-dars-parchment-deep"
            >
              ← Back
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={busy}
              className="px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
            >
              {busy ? "Saving…" : "Confirm onboarding"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
