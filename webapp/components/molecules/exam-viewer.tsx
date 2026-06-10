/**
 * F-3.4 — Exam viewer.
 *
 * Fetches slots.getAssessmentSlotDetail() and renders the generated formative
 * exam. Mirrors LPViewer's structure + status handling:
 *   - not_generated → prompt to generate from the timeline row
 *   - PENDING / IN_FLIGHT → "generating" stripe (the row's poll loop drives the
 *     status forward; re-opening re-fetches)
 *   - ERROR → the upstream error message
 *   - READY → the exam paper HTML (UG_EG-rendered)
 *
 * No per-slot config editor here (D-10) — the FA uses the per-subject Default
 * FA Config. Mastery entry lands separately (F4.13).
 */
"use client";

import { useEffect, useState } from "react";

import {
  slots,
  type ClassAssessmentSlotDetail,
  DarsApiError,
} from "@/lib/dars-api";

interface ExamViewerProps {
  slotId: string;
}

export function ExamViewer({ slotId }: ExamViewerProps) {
  const [detail, setDetail] = useState<ClassAssessmentSlotDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await slots.getAssessmentSlotDetail(slotId);
        if (cancelled) return;
        setDetail(next);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        const msg =
          err instanceof DarsApiError
            ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
            : err instanceof Error
              ? err.message
              : "Failed to load exam";
        setError(msg);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slotId]);

  if (error) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <strong className="font-semibold">Couldn’t load exam.</strong>
        <p className="text-dars-muted mt-1">{error}</p>
      </div>
    );
  }

  if (!detail) {
    return <LoadingStripe label="Loading exam…" />;
  }

  if (detail.exam_status === "not_generated") {
    return (
      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-ink">
        <p className="font-medium">No exam generated yet.</p>
        <p className="text-xs text-dars-muted mt-2">
          Use “Generate exam” on this assessment to create a short formative
          quiz from its covered topics.
        </p>
      </div>
    );
  }

  if (detail.exam_status === "PENDING" || detail.exam_status === "IN_FLIGHT") {
    return <LoadingStripe label="Generating exam…" />;
  }

  if (detail.exam_status === "ERROR") {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <strong className="font-semibold">Exam generation failed.</strong>
        <p className="text-dars-muted mt-1">
          {detail.exam_error_message ?? "The exam generator returned an error."}
        </p>
      </div>
    );
  }

  // READY — render the UG_EG-produced exam paper.
  if (!detail.exam_paper_html) {
    return (
      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-muted">
        Exam is ready, but no paper HTML was returned.
      </div>
    );
  }

  return (
    <article
      className="prose prose-sm max-w-none text-dars-ink leading-relaxed"
      dangerouslySetInnerHTML={{ __html: detail.exam_paper_html }}
    />
  );
}

function LoadingStripe({ label }: { label: string }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-muted">
      <div className="flex items-center gap-3">
        <div className="h-2 w-2 rounded-full bg-dars-terra animate-pulse" />
        {label}
      </div>
    </div>
  );
}
