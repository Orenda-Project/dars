/**
 * F4.4 — /teacher-app/today
 *
 * Owns data fetching, slide-over state, and mark-taught.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import { LPViewer } from "@/components/molecules/lp-viewer";
import { SlideOver } from "@/components/molecules/slide-over";
import { TodayTemplate } from "@/components/templates/today-template";
import {
  DarsApiError,
  slots as slotsApi,
  today as todayApi,
  type AssessmentSlotEntry,
  type LessonSlotEntry,
  type TodayEntry,
  type TodayResponse,
} from "@/lib/dars-api";

type Drawer =
  | { kind: "lp"; slotId: string; title: string; subtitle: string }
  | { kind: "exam"; slot: AssessmentSlotEntry; title: string; subtitle: string }
  | null;

export default function TodayPage() {
  const [today, setToday] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [busySlotId, setBusySlotId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setToday(await todayApi.get());
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed to load today",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onViewLP = (slot: LessonSlotEntry, ctx: TodayEntry) => {
    setDrawer({
      kind: "lp",
      slotId: slot.slot_id,
      title: slot.slot_type === "revision" ? "Revision LP" : "Lesson plan",
      subtitle: `Grade ${ctx.grade_code} · ${ctx.subject_code} · Day ${slot.position}`,
    });
  };

  const onViewExam = (slot: AssessmentSlotEntry, ctx: TodayEntry) => {
    setDrawer({
      kind: "exam",
      slot,
      title: slot.assessment_type === "formative" ? "Formative assessment" : "Summative assessment",
      subtitle: `Grade ${ctx.grade_code} · ${ctx.subject_code} · ${slot.topic_ids.length} topic${slot.topic_ids.length === 1 ? "" : "s"}`,
    });
  };

  const onMarkTaught = async (slot: LessonSlotEntry, _ctx: TodayEntry) => {
    setBusySlotId(slot.slot_id);
    try {
      const today = new Date().toISOString().slice(0, 10);
      await slotsApi.markTaught(slot.slot_id, { taught_on: today });
      await load();
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `Mark-taught failed (${err.status}): ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Mark-taught failed",
      );
    } finally {
      setBusySlotId(null);
    }
  };

  return (
    <>
      <TodayTemplate
        today={today}
        loading={loading}
        error={error}
        onViewLP={onViewLP}
        onMarkTaught={onMarkTaught}
        onViewExam={onViewExam}
        busySlotId={busySlotId}
      />

      <SlideOver
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title={drawer?.title ?? ""}
        subtitle={drawer?.subtitle}
      >
        {drawer?.kind === "lp" ? <LPViewer slotId={drawer.slotId} /> : null}
        {drawer?.kind === "exam" ? (
          <ExamPlaceholder slot={drawer.slot} />
        ) : null}
      </SlideOver>
    </>
  );
}

function ExamPlaceholder({ slot }: { slot: AssessmentSlotEntry }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-ink">
      <p className="font-medium">Exam viewer coming in F4.7.</p>
      <p className="text-xs text-dars-muted mt-2">
        Backend supplies the exam JSON + HTML via the generated_exam linked to
        this slot ({slot.slot_id.slice(0, 8)}…). For now the today page only
        surfaces the LP slide-over.
      </p>
    </div>
  );
}
