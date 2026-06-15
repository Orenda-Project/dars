/**
 * F4.13 — Mastery entry form.
 *
 * Loads the assessment slot detail (which includes the exam JSON),
 * walks the question tree, lets the teacher enter students_correct per
 * question, then submits to POST /class-assessment-slots/{id}/results.
 *
 * dynamic-chapter-planner F-3.3 — after a successful submit (and on load if the
 * slot was already graded), we fetch the reteach suggestion for this FA slot.
 * If the class fell below the mastery threshold on any sub-SLO, a confirm panel
 * appears so the teacher can re-cover it (lightweight) or add a reteach lesson
 * (heavy). Reteach NEVER auto-applies (D-9).
 */
"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

import {
  MasteryEntryTemplate,
  type MasteryEntryRow,
} from "@/components/templates/mastery-entry-template";
import {
  emptyReteachItemState,
  ReteachPanel,
  type ReteachItemState,
  type ReteachMode,
} from "@/components/molecules/reteach-panel";
import {
  DarsApiError,
  mastery as masteryApi,
  slots as slotsApi,
  type ClassAssessmentSlotDetail,
  type ReteachSuggestionResponse,
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

  // Reteach suggestion (F-3.3). Null until fetched; empty items ⇒ no panel.
  const [suggestion, setSuggestion] = useState<ReteachSuggestionResponse | null>(
    null,
  );
  // Per-sub-SLO confirm/outcome state, keyed by sub_slo_id.
  const [reteachStates, setReteachStates] = useState<
    Record<string, ReteachItemState>
  >({});

  // Fetch the reteach suggestion for this slot. Quiet — a missing/empty
  // suggestion simply means no panel, never an error toast on this page.
  const fetchSuggestion = useCallback(async () => {
    try {
      const s = await slotsApi.getReteachSuggestion(slotId);
      setSuggestion(s);
    } catch {
      // Non-fatal: leave the panel hidden if the read fails.
      setSuggestion(null);
    }
  }, [slotId]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await slotsApi.getAssessmentSlotDetail(slotId);
      setDetail(d);
      const questions = walkExamQuestions(d.exam_result);
      setRows(questions.map((q) => ({ question: q, studentsCorrect: "" })));
      // If the slot is already graded, surface any below-threshold sub-SLOs so
      // a teacher returning to a graded slot still sees the reteach panel.
      if (d.status === "completed") {
        await fetchSuggestion();
      }
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setLoading(false);
    }
  }, [slotId, fetchSuggestion]);

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
      // F-3.3: grading is done — fetch the reteach suggestion. If the class fell
      // below threshold on any sub-SLO, the panel renders below and the teacher
      // stays on this page to act on it (no auto-navigate when there's a
      // suggestion to handle).
      const s = await slotsApi.getReteachSuggestion(slotId).catch(() => null);
      setSuggestion(s);
      if (!s || s.items.length === 0) {
        // Nothing to reteach — return to the assessments tab as before.
        setTimeout(() => {
          router.replace(`/teacher-app/classes/${cstId}?tab=assessments`);
        }, 1200);
      }
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  function patchReteachState(subSloId: string, patch: Partial<ReteachItemState>) {
    setReteachStates((prev) => ({
      ...prev,
      [subSloId]: { ...(prev[subSloId] ?? emptyReteachItemState()), ...patch },
    }));
  }

  function handleSelectMode(subSloId: string, mode: ReteachMode) {
    patchReteachState(subSloId, { mode });
  }

  function handleDecline(subSloId: string) {
    patchReteachState(subSloId, { declined: true, error: null });
  }

  async function handleConfirmReteach(subSloId: string) {
    const current = reteachStates[subSloId] ?? emptyReteachItemState();
    patchReteachState(subSloId, { busy: true, error: null });
    try {
      const result = await slotsApi.confirmReteach(slotId, {
        sub_slo_id: subSloId,
        mode: current.mode,
      });
      // Acted: record the result and disable further action on this sub-SLO.
      patchReteachState(subSloId, { busy: false, result });
    } catch (err) {
      patchReteachState(subSloId, { busy: false, error: formatErr(err) });
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

  const showReteach = suggestion !== null && suggestion.items.length > 0;

  return (
    <div className="space-y-6">
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

      {showReteach ? (
        <ReteachPanel
          threshold={suggestion.threshold}
          items={suggestion.items}
          states={reteachStates}
          onSelectMode={handleSelectMode}
          onConfirm={handleConfirmReteach}
          onDecline={handleDecline}
        />
      ) : null}
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
