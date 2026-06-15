/**
 * lp-context-header Phase 3 (F-3.1 / F-3.2) — Chapter Page.
 *
 * A dedicated teacher-app page for one syllabus chapter, replacing the
 * inline-accordion expand that used to live on the Syllabus tab (D-8).
 *
 * Self-fetching client component (D-10): it reads `cst_id` + `position` from
 * the URL and fetches `getSyllabus` + `getTimeline` on mount, so it survives
 * refresh, direct links, and back/forward — it relies on NO parent state. The
 * page shell + back link paint immediately; a light skeleton fills the body
 * until both fetches land.
 *
 * Keyed by chapter `position` (D-9): the chapter is `chapters.find(c =>
 * c.position === pos)` and its slots are the timeline items whose
 * `breakdown_chapter_position === pos`.
 *
 * The body reuses {@link ChapterContents} (D-11) — the same renderer the
 * Syllabus tab used to use — so the row affordances (View LP, View exam, Mark
 * taught, Skip, Generate LP/exam + poll, "Now" marker) are a SUPERSET of what
 * the old accordion offered. The page owns the same slot-action state +
 * handlers + slide-over the class detail page owns; their `refetch` reloads
 * THIS page's timeline.
 */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { ExamViewer } from "@/components/molecules/exam-viewer";
import { LPViewer } from "@/components/molecules/lp-viewer";
import { SlideOver } from "@/components/molecules/slide-over";
import type { TimelineRowCallbacks } from "@/components/templates/class-timeline-tab";
import {
  ChapterContents,
  ChapterStatusBadge,
  formatDate,
} from "@/components/templates/class-syllabus-tab";
import {
  DarsApiError,
  slots as slotsApi,
  type ClassPathChapter,
  type CstTimelineItem,
  type SyllabusForCstResponse,
  type TodayEntry,
  today as todayApi,
} from "@/lib/dars-api";

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed to load";
}

export default function ChapterPage() {
  const params = useParams<{ cst_id: string; position: string }>();
  const cstId = params.cst_id;
  const pos = Number(params.position);

  // ----- Self-fetched data (D-10) -----
  const [syllabus, setSyllabus] = useState<SyllabusForCstResponse | null>(null);
  const [syllabusError, setSyllabusError] = useState<string | null>(null);
  const [timeline, setTimeline] = useState<CstTimelineItem[] | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  // Today entry pins the "Now" marker (mirrors the class detail page).
  const [todayEntry, setTodayEntry] = useState<TodayEntry | null>(null);

  const loadSyllabus = useCallback(async () => {
    setSyllabusError(null);
    try {
      const res = await slotsApi.getSyllabus(cstId);
      setSyllabus(res);
    } catch (err) {
      setSyllabusError(formatErr(err));
    }
  }, [cstId]);

  const loadTimeline = useCallback(async () => {
    setTimelineError(null);
    try {
      const res = await slotsApi.getTimeline(cstId);
      setTimeline(res.items);
    } catch (err) {
      setTimelineError(formatErr(err));
    }
  }, [cstId]);

  // Mount: fetch syllabus + timeline (+ today entry) in parallel, with the
  // cancel guard the class detail loaders use.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [syl, tl, td] = await Promise.allSettled([
        slotsApi.getSyllabus(cstId),
        slotsApi.getTimeline(cstId),
        todayApi.get(),
      ]);
      if (cancelled) return;
      if (syl.status === "fulfilled") setSyllabus(syl.value);
      else setSyllabusError(formatErr(syl.reason));
      if (tl.status === "fulfilled") setTimeline(tl.value.items);
      else setTimelineError(formatErr(tl.reason));
      if (td.status === "fulfilled") {
        setTodayEntry(td.value.items.find((e) => e.cst_id === cstId) ?? null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cstId]);

  // ----- Resolve this chapter + its slots (D-9) -----
  const chapter: ClassPathChapter | undefined = useMemo(
    () => syllabus?.chapters.find((c) => c.position === pos),
    [syllabus, pos],
  );

  const items = useMemo<CstTimelineItem[]>(() => {
    if (!timeline) return [];
    return [...timeline]
      .filter((t) => t.breakdown_chapter_position === pos)
      .sort((a, b) => a.position - b.position);
  }, [timeline, pos]);

  // ----- Slide-over + slot-action state (copied from the class detail page) --
  const [drawer, setDrawer] = useState<{
    kind: "lp" | "exam";
    slotId: string;
    title: string;
    subtitle: string;
  } | null>(null);
  const [busySlotId, setBusySlotId] = useState<string | null>(null);
  const [generatingSlotId, setGeneratingSlotId] = useState<string | null>(null);
  const [generatingExamSlotId, setGeneratingExamSlotId] = useState<string | null>(
    null,
  );

  function openLP(slot: Extract<CstTimelineItem, { kind: "lesson" }>) {
    setDrawer({
      kind: "lp",
      slotId: slot.id,
      title: slot.slot_type === "revision" ? "Revision LP" : "Lesson plan",
      subtitle: `Day ${slot.position} · ${slot.topic_title ?? "—"}`,
    });
  }

  const markTaughtById = useCallback(
    async (slotId: string) => {
      setBusySlotId(slotId);
      try {
        const today = new Date().toISOString().slice(0, 10);
        await slotsApi.markTaught(slotId, { taught_on: today });
        // Refetch the timeline (status/lp_status change) + syllabus (chapter
        // status + slot_count can change).
        await Promise.all([loadTimeline(), loadSyllabus()]);
      } catch (err) {
        setTimelineError(formatErr(err));
      } finally {
        setBusySlotId(null);
      }
    },
    [loadTimeline, loadSyllabus],
  );

  const onTimelineViewLP = useCallback(
    (item: Extract<CstTimelineItem, { kind: "lesson" }>) => openLP(item),
    [],
  );

  const onTimelineViewExam = useCallback(
    (item: Extract<CstTimelineItem, { kind: "assessment" }>) => {
      setDrawer({
        kind: "exam",
        slotId: item.id,
        title:
          item.assessment_type === "formative"
            ? "Formative assessment"
            : "Summative assessment",
        subtitle: `Day ${item.position} · ${item.topic_titles.length} topic${item.topic_titles.length === 1 ? "" : "s"}`,
      });
    },
    [],
  );

  const onTimelineMarkTaught = useCallback(
    async (item: CstTimelineItem) => {
      if (item.kind === "lesson") {
        await markTaughtById(item.id);
        return;
      }
      // Assessment "mark done" → complete.
      setBusySlotId(item.id);
      try {
        const today = new Date().toISOString().slice(0, 10);
        await slotsApi.completeAssessment(item.id, { taught_on: today });
        await Promise.all([loadTimeline(), loadSyllabus()]);
      } catch (err) {
        setTimelineError(formatErr(err));
      } finally {
        setBusySlotId(null);
      }
    },
    [markTaughtById, loadTimeline, loadSyllabus],
  );

  const onTimelineSkip = useCallback(
    async (item: CstTimelineItem) => {
      setBusySlotId(item.id);
      try {
        const today = new Date().toISOString().slice(0, 10);
        if (item.kind === "lesson") {
          await slotsApi.skipLesson(item.id, { occurred_on: today });
        } else {
          await slotsApi.skipAssessment(item.id, { occurred_on: today });
        }
        await Promise.all([loadTimeline(), loadSyllabus()]);
      } catch (err) {
        setTimelineError(formatErr(err));
      } finally {
        setBusySlotId(null);
      }
    },
    [loadTimeline, loadSyllabus],
  );

  // On-demand LP generation for a lesson slot (Generate / Retry). Dispatch,
  // then poll the slot detail until READY/ERROR, refetching this page's
  // timeline each tick so the status pill + button stay live. Idempotent — a
  // cache hit returns a terminal status on the first response and skips polling.
  const generateLPAndPoll = useCallback(
    async (slotId: string, refetch: () => Promise<void>) => {
      setGeneratingSlotId(slotId);
      try {
        const created = await slotsApi.generateLPForSlot(slotId);
        await refetch();

        let status: string = created.lp_status;
        const POLL_MS = 3000;
        const MAX_POLLS = 40;
        let polls = 0;
        while (status !== "READY" && status !== "ERROR" && polls < MAX_POLLS) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          polls += 1;
          const detail = await slotsApi.getLessonSlotDetail(slotId);
          status = detail.lp_status;
          await refetch();
        }
      } finally {
        setGeneratingSlotId(null);
      }
    },
    [],
  );

  const onTimelineGenerateLP = useCallback(
    async (item: Extract<CstTimelineItem, { kind: "lesson" }>) => {
      setTimelineError(null);
      try {
        await generateLPAndPoll(item.id, loadTimeline);
      } catch (err) {
        setTimelineError(formatErr(err));
      }
    },
    [generateLPAndPoll, loadTimeline],
  );

  // On-demand FA exam generation for an assessment slot (Generate / Retry).
  const generateExamAndPoll = useCallback(
    async (slotId: string, refetch: () => Promise<void>) => {
      setGeneratingExamSlotId(slotId);
      try {
        const created = await slotsApi.generateExamForSlot(slotId);
        await refetch();

        let status: string = created.exam_status;
        const POLL_MS = 3000;
        const MAX_POLLS = 40;
        let polls = 0;
        while (status !== "READY" && status !== "ERROR" && polls < MAX_POLLS) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          polls += 1;
          const detail = await slotsApi.getAssessmentSlotDetail(slotId);
          status = detail.exam_status;
          await refetch();
        }
      } finally {
        setGeneratingExamSlotId(null);
      }
    },
    [],
  );

  const onTimelineGenerateExam = useCallback(
    async (item: Extract<CstTimelineItem, { kind: "assessment" }>) => {
      setTimelineError(null);
      try {
        await generateExamAndPoll(item.id, loadTimeline);
      } catch (err) {
        setTimelineError(formatErr(err));
      }
    },
    [generateExamAndPoll, loadTimeline],
  );

  // Row callbacks the chapter contents thread straight through to each row.
  const rowCallbacks = useMemo<TimelineRowCallbacks>(
    () => ({
      onViewLP: onTimelineViewLP,
      onViewExam: onTimelineViewExam,
      onMarkTaught: onTimelineMarkTaught,
      onSkip: onTimelineSkip,
      onGenerateLP: onTimelineGenerateLP,
      onGenerateExam: onTimelineGenerateExam,
    }),
    [
      onTimelineViewLP,
      onTimelineViewExam,
      onTimelineMarkTaught,
      onTimelineSkip,
      onTimelineGenerateLP,
      onTimelineGenerateExam,
    ],
  );

  // "You are here" (D-7): today's slot if scheduled, else the first
  // not-yet-done item in teaching order.
  const currentSlotId = useMemo<string | null>(() => {
    if (!timeline) return null;
    const todaySlotId =
      todayEntry?.lesson_slot?.slot_id ??
      todayEntry?.assessment_slot?.slot_id ??
      null;
    if (todaySlotId && timeline.some((t) => t.id === todaySlotId)) {
      return todaySlotId;
    }
    const pending = timeline.find(
      (t) => t.status === "planned" || t.status === "scheduled",
    );
    return pending?.id ?? null;
  }, [timeline, todayEntry]);

  // ----- Render (D-10): shell + back link paint immediately. -----
  const loading = syllabus === null;
  const notFound = !loading && chapter === undefined;

  return (
    <>
      <div className="mb-2 text-sm text-dars-muted">
        <Link
          href={`/teacher-app/classes/${cstId}?tab=syllabus`}
          className="hover:text-dars-terra"
        >
          ← Back to syllabus
        </Link>
      </div>

      {syllabusError ? (
        <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
          <p className="text-sm font-semibold text-dars-ink">
            Couldn&rsquo;t load this chapter
          </p>
          <p className="text-xs text-dars-muted mt-1">{syllabusError}</p>
        </div>
      ) : loading ? (
        <p className="text-sm text-dars-muted">Loading chapter…</p>
      ) : notFound ? (
        <div className="rounded-md border border-dashed border-dars-rule-light bg-dars-parchment p-6 text-center">
          <p className="text-sm font-medium text-dars-ink">Chapter not found</p>
          <p className="text-xs text-dars-muted mt-1">
            This chapter isn&rsquo;t in the class syllabus.{" "}
            <Link
              href={`/teacher-app/classes/${cstId}?tab=syllabus`}
              className="text-dars-terra hover:underline"
            >
              Back to syllabus
            </Link>
            .
          </p>
        </div>
      ) : (
        <>
          {/* Header — chapter number + title + the same summary PathRow shows. */}
          <header className="mb-5">
            <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
              Ch {chapter!.chapter_number} · {chapter!.title}
            </h1>
            <div className="mt-2 flex items-center gap-2 flex-wrap">
              <ChapterStatusBadge status={chapter!.status} />
              {chapter!.slot_count > 0 ? (
                <span className="text-xs text-dars-muted">
                  {chapter!.slot_count} period
                  {chapter!.slot_count === 1 ? "" : "s"}
                </span>
              ) : null}
              <span className="flex items-center gap-1 text-xs text-dars-ink-soft">
                <span className="font-mono">{formatDate(chapter!.start_date)}</span>
                <span className="text-dars-muted-light">→</span>
                <span className="font-mono">{formatDate(chapter!.end_date)}</span>
              </span>
            </div>
          </header>

          {timelineError ? (
            <div className="mb-4 rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
              <p className="text-sm font-semibold text-dars-ink">
                Something went wrong
              </p>
              <p className="text-xs text-dars-muted mt-1">{timelineError}</p>
            </div>
          ) : null}

          <ChapterContents
            brokenDown={chapter!.is_generated}
            items={items}
            timelineLoading={timeline === null}
            currentSlotId={currentSlotId}
            rowCallbacks={rowCallbacks}
            generatingSlotId={generatingSlotId}
            generatingExamSlotId={generatingExamSlotId}
            busySlotId={busySlotId}
          />
        </>
      )}

      <SlideOver
        open={drawer !== null}
        onClose={() => setDrawer(null)}
        title={drawer?.title ?? ""}
        subtitle={drawer?.subtitle}
      >
        {drawer?.kind === "lp" ? <LPViewer slotId={drawer.slotId} /> : null}
        {drawer?.kind === "exam" ? <ExamViewer slotId={drawer.slotId} /> : null}
      </SlideOver>
    </>
  );
}
