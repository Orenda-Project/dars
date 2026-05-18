/**
 * F4.13 — Mastery entry form.
 *
 * Loads the assessment slot detail (which includes the exam JSON),
 * walks the question tree, lets the teacher enter students_correct per
 * question, then submits to POST /class-assessment-slots/{id}/results.
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import {
  MasteryEntryTemplate,
  type MasteryEntryRow,
} from "@/components/templates/mastery-entry-template";
import {
  DarsApiError,
  mastery as masteryApi,
  slots as slotsApi,
  type ClassAssessmentSlotDetail,
} from "@/lib/dars-api";
import { walkExamQuestions } from "@/lib/exam-walker";

export default function MasteryEntryPage() {
  const params = useParams<{ cst_id: string; slot_id: string }>();
  const slotId = params.slot_id;
  const cstId = params.cst_id;
  const router = useRouter();

  const [detail, setDetail] = useState<ClassAssessmentSlotDetail | null>(null);
  const [rows, setRows] = useState<MasteryEntryRow[]>([]);
  const [studentsPresent, setStudentsPresent] = useState<number | "">(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await slotsApi.getAssessmentSlotDetail(slotId);
      setDetail(d);
      const questions = walkExamQuestions(d.exam_result);
      setRows(questions.map((q) => ({ question: q, studentsCorrect: "" })));
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setLoading(false);
    }
  }, [slotId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSubmit() {
    setError(null);
    setSuccess(null);
    if (studentsPresent === "" || studentsPresent <= 0) {
      setError("Enter how many students were present.");
      return;
    }
    const incomplete = rows.filter((r) => r.studentsCorrect === "");
    if (incomplete.length > 0) {
      setError(`${incomplete.length} question(s) still missing answers.`);
      return;
    }
    setBusy(true);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const resp = await masteryApi.submitExamResults(slotId, {
        students_present: Number(studentsPresent),
        assessed_on: today,
        per_question: rows.map((r) => ({
          question_index: r.question.index,
          students_correct: Number(r.studentsCorrect),
        })),
      });
      setSuccess(
        `Saved. ${resp.sub_slo_mastery_rows} sub-SLO mastery row${resp.sub_slo_mastery_rows === 1 ? "" : "s"} updated.`,
      );
      // After a beat, navigate back to the assessments tab.
      setTimeout(() => {
        router.replace(`/teacher-app/classes/${cstId}?tab=assessments`);
      }, 1200);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-sm text-dars-muted">Loading exam…</p>;
  if (error && !detail) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
        <p className="text-sm font-semibold text-dars-ink">Couldn’t load.</p>
        <p className="text-xs text-dars-muted mt-1">{error}</p>
      </div>
    );
  }

  if (!detail || detail.exam_status !== "READY") {
    return (
      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-ink">
        <p className="font-medium">Exam not ready</p>
        <p className="text-xs text-dars-muted mt-1">
          Exam status: <strong>{detail?.exam_status ?? "unknown"}</strong>.
          {" "}
          Wait for it to finish generating before recording results.
        </p>
      </div>
    );
  }

  return (
    <MasteryEntryTemplate
      defaultStudentsPresent={30}
      rows={rows}
      setRows={setRows}
      studentsPresent={studentsPresent}
      setStudentsPresent={setStudentsPresent}
      onSubmit={handleSubmit}
      busy={busy}
      error={error}
      successMessage={success}
    />
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
