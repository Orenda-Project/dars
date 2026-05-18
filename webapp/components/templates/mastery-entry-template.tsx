/**
 * F4.13 — Mastery entry form template.
 *
 * Pure layout. Page resolves the questions list and owns the submit
 * handler; this just renders the form.
 */
"use client";

import { useState } from "react";

import type { ExamQuestionWalkItem } from "@/lib/exam-walker";

export interface MasteryEntryRow {
  question: ExamQuestionWalkItem;
  /** "" while unset; number once typed. */
  studentsCorrect: number | "";
}

interface MasteryEntryTemplateProps {
  defaultStudentsPresent: number;
  rows: MasteryEntryRow[];
  setRows: (next: MasteryEntryRow[]) => void;
  studentsPresent: number | "";
  setStudentsPresent: (n: number | "") => void;
  onSubmit: () => Promise<void>;
  busy: boolean;
  error: string | null;
  successMessage: string | null;
}

export function MasteryEntryTemplate(props: MasteryEntryTemplateProps) {
  const {
    rows,
    setRows,
    studentsPresent,
    setStudentsPresent,
    onSubmit,
    busy,
    error,
    successMessage,
  } = props;

  if (rows.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
        <p className="text-sm font-medium text-dars-ink">No questions to record</p>
        <p className="text-xs text-dars-muted mt-1">
          The exam JSON is empty or still generating. Once it's ready,
          questions will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <header>
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
          Record assessment results
        </h1>
        <p className="text-sm text-dars-muted mt-1">
          For each question, enter how many students got it right.
        </p>
      </header>

      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
        <label className="block">
          <span className="text-sm font-medium text-dars-ink-soft">
            Students present
          </span>
          <input
            type="number"
            min={1}
            value={studentsPresent}
            onChange={(e) =>
              setStudentsPresent(e.target.value === "" ? "" : Number(e.target.value))
            }
            className="mt-1 w-32 px-3 py-2 rounded-md border border-dars-rule-light bg-white text-dars-ink text-sm"
          />
        </label>
      </div>

      <ol className="space-y-2">
        {rows.map((row, i) => (
          <li
            key={row.question.key}
            className="rounded-md border border-dars-rule-light bg-dars-parchment p-3"
          >
            <div className="flex items-baseline gap-2 mb-2">
              <span className="font-mono text-xs text-dars-muted">
                Q{i + 1}
              </span>
              {row.question.marks !== null ? (
                <span className="text-[10px] text-dars-muted-light font-mono">
                  {row.question.marks} mark{row.question.marks === 1 ? "" : "s"}
                </span>
              ) : null}
              <span className="text-[10px] text-dars-muted-light font-mono ml-auto">
                {row.question.key}
              </span>
            </div>
            <p className="text-sm text-dars-ink mb-3 whitespace-pre-line">
              {row.question.text}
            </p>
            <label className="flex items-center gap-2 text-xs text-dars-ink-soft">
              <span>How many got it right?</span>
              <input
                type="number"
                min={0}
                max={typeof studentsPresent === "number" ? studentsPresent : undefined}
                value={row.studentsCorrect}
                onChange={(e) => {
                  const next = [...rows];
                  next[i] = {
                    ...row,
                    studentsCorrect: e.target.value === "" ? "" : Number(e.target.value),
                  };
                  setRows(next);
                }}
                className="w-20 px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
              />
              <span>
                / {studentsPresent === "" ? "—" : studentsPresent}
              </span>
            </label>
          </li>
        ))}
      </ol>

      {error ? (
        <p className="text-sm text-dars-terra" role="alert">
          {error}
        </p>
      ) : null}
      {successMessage ? (
        <p className="text-sm text-emerald-700" role="status">
          {successMessage}
        </p>
      ) : null}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy}
          className="px-4 py-2 rounded-md bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Saving…" : "Save & Submit"}
        </button>
      </div>
    </div>
  );
}
