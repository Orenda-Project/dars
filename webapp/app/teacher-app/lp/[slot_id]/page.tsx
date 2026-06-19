/**
 * Teacher-App LP View — open a single lesson plan and follow generation to
 * completion. Reached from the class page's "Generate LP" action (D-8).
 *
 * Flow (see docs/features/teacher-app-lp-view-polling/):
 *   - On mount, fetch the slot once and branch on lp_status (D-7):
 *       not_generated → fire generate-lp, then poll
 *       PENDING / IN_FLIGHT → poll (do NOT re-fire generate)
 *       READY → render lp_content
 *       ERROR → show message + Retry
 *   - Poll GET /api/v1/class-lesson-slots/{id} every 5s (D-3) until the
 *     status is READY/ERROR, or a ~10-min safety ceiling (D-6) — a dropped
 *     callback leaves the slot IN_FLIGHT forever and must not pin the tab.
 *   - ERROR (D-4): stop, show lp_error_message + Retry (re-fires generate-lp,
 *     which is idempotent, then resumes polling).
 *
 * Frontend-only: reuses slots.getLessonSlotDetail / slots.generateLPForSlot.
 * The LP body is lp_content rendered directly — NOT the LPViewer molecule,
 * which renders a hardcoded stub and ignores status (D-5). Mirrors the
 * status machine + prose rendering of components/molecules/exam-viewer.tsx.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { LpContextHeader } from "@/components/molecules/lp-context-header";
import {
  slots,
  DarsApiError,
  type ClassLessonSlotDetail,
} from "@/lib/dars-api";

const POLL_MS = 5000; // D-3 — 5-second poll cadence
const MAX_POLLS = 120; // D-6 — ~10 min ceiling (120 × 5s) before we stop

type LpStatus = ClassLessonSlotDetail["lp_status"];

function isPending(status: LpStatus): boolean {
  return status === "PENDING" || status === "IN_FLIGHT";
}

export default function TeacherLpViewPage() {
  const params = useParams<{ slot_id: string }>();
  const slotId = params.slot_id;

  const [detail, setDetail] = useState<ClassLessonSlotDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  // True once we hit MAX_POLLS while still pending (D-6) — distinct from a
  // server-side ERROR; the slot is genuinely still generating.
  const [pollExhausted, setPollExhausted] = useState(false);

  // Guards so a poll loop never sets state after unmount and we never run two
  // loops at once (e.g. Retry / Keep-checking re-arming).
  const aliveRef = useRef(true);
  const loopRef = useRef(0);

  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
    };
  }, []);

  const sleep = (ms: number) =>
    new Promise<void>((resolve) => setTimeout(resolve, ms));

  /**
   * Poll the slot detail every POLL_MS until READY/ERROR or the ceiling.
   * `myLoop` tags this invocation; if a newer loop starts (or we unmount),
   * this one exits quietly without touching state.
   */
  const pollUntilTerminal = useCallback(
    async (initial: ClassLessonSlotDetail) => {
      const myLoop = ++loopRef.current;
      let current = initial;
      let polls = 0;
      while (
        aliveRef.current &&
        loopRef.current === myLoop &&
        isPending(current.lp_status) &&
        polls < MAX_POLLS
      ) {
        await sleep(POLL_MS);
        if (!aliveRef.current || loopRef.current !== myLoop) return;
        polls += 1;
        try {
          current = await slots.getLessonSlotDetail(slotId);
        } catch (err) {
          if (!aliveRef.current || loopRef.current !== myLoop) return;
          setLoadError(formatErr(err));
          return; // transient fetch failure — surface it, stop this loop
        }
        if (!aliveRef.current || loopRef.current !== myLoop) return;
        setDetail(current);
      }
      if (
        aliveRef.current &&
        loopRef.current === myLoop &&
        isPending(current.lp_status) &&
        polls >= MAX_POLLS
      ) {
        setPollExhausted(true); // D-6 — stop, offer "Keep checking"
      }
    },
    [slotId],
  );

  // Mount: fetch once, then branch on status (D-7).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let next = await slots.getLessonSlotDetail(slotId);
        if (cancelled) return;

        // Auto-start generation only if it has never been generated (D-7).
        if (next.lp_status === "not_generated") {
          const created = await slots.generateLPForSlot(slotId);
          if (cancelled) return;
          // generate-lp returns the fresh status; reflect it, then re-read the
          // full detail so the header/content fields are populated.
          next = { ...next, lp_status: created.lp_status };
          setDetail(next);
          try {
            next = await slots.getLessonSlotDetail(slotId);
            if (cancelled) return;
          } catch {
            /* keep the generate response; poll loop will refresh */
          }
        }

        if (cancelled) return;
        setDetail(next);
        setLoadError(null);
        if (isPending(next.lp_status)) {
          void pollUntilTerminal(next);
        }
      } catch (err) {
        if (cancelled) return;
        setLoadError(formatErr(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [slotId, pollUntilTerminal]);

  // Retry (D-4) — re-fire generate (idempotent) and resume polling.
  const onRetry = useCallback(async () => {
    setRetrying(true);
    setLoadError(null);
    setPollExhausted(false);
    try {
      const created = await slots.generateLPForSlot(slotId);
      const next = await slots.getLessonSlotDetail(slotId);
      if (!aliveRef.current) return;
      setDetail(next);
      if (isPending(next.lp_status) || isPending(created.lp_status)) {
        void pollUntilTerminal(next);
      }
    } catch (err) {
      if (!aliveRef.current) return;
      setLoadError(formatErr(err));
    } finally {
      if (aliveRef.current) setRetrying(false);
    }
  }, [slotId, pollUntilTerminal]);

  // "Keep checking" (D-6) — re-arm the poll loop after the ceiling.
  const onKeepChecking = useCallback(() => {
    if (!detail) return;
    setPollExhausted(false);
    void pollUntilTerminal(detail);
  }, [detail, pollUntilTerminal]);

  return (
    <div className="max-w-3xl space-y-5">
      <div>
        <Link
          href={
            detail ? `/teacher-app/classes/${detail.cst_id}` : "/teacher-app/classes"
          }
          className="text-xs text-dars-muted hover:text-dars-ink"
        >
          ← Back to class
        </Link>
      </div>

      <header className="space-y-3">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
          Lesson plan
        </h1>
        {detail ? (
          <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
            <LpContextHeader
              chapterNumber={detail.chapter_number}
              chapterTitle={detail.chapter_title}
              topicTitle={detail.topic_text}
              lpType={detail.lp_type}
            />
          </div>
        ) : null}
      </header>

      <Body
        detail={detail}
        loadError={loadError}
        retrying={retrying}
        pollExhausted={pollExhausted}
        onRetry={onRetry}
        onKeepChecking={onKeepChecking}
      />
    </div>
  );
}

function Body({
  detail,
  loadError,
  retrying,
  pollExhausted,
  onRetry,
  onKeepChecking,
}: {
  detail: ClassLessonSlotDetail | null;
  loadError: string | null;
  retrying: boolean;
  pollExhausted: boolean;
  onRetry: () => void;
  onKeepChecking: () => void;
}) {
  if (loadError) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <strong className="font-semibold">Couldn’t load the lesson plan.</strong>
        <p className="text-dars-muted mt-1">{loadError}</p>
        <RetryButton retrying={retrying} onClick={onRetry} />
      </div>
    );
  }

  if (!detail) {
    return <GeneratingStripe label="Loading lesson plan…" />;
  }

  // ERROR (D-4) — stop polling, show the message + Retry.
  if (detail.lp_status === "ERROR") {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <strong className="font-semibold">Lesson plan generation failed.</strong>
        <p className="text-dars-muted mt-1">
          {detail.lp_error_message ??
            "The lesson-plan generator returned an error."}
        </p>
        <RetryButton retrying={retrying} onClick={onRetry} />
      </div>
    );
  }

  // Pending / in-flight — generating state. Poll ceiling reached (D-6) swaps
  // the affordance to "Keep checking".
  if (
    detail.lp_status === "PENDING" ||
    detail.lp_status === "IN_FLIGHT" ||
    detail.lp_status === "not_generated"
  ) {
    if (pollExhausted) {
      return (
        <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-ink">
          <p className="font-medium">Still generating — taking longer than usual.</p>
          <p className="text-xs text-dars-muted mt-2">
            The lesson plan hasn’t come back yet. It may still be processing
            upstream. You can keep checking, or come back to this page later.
          </p>
          <button
            type="button"
            onClick={onKeepChecking}
            className="mt-3 px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-sm font-semibold hover:opacity-90"
          >
            Keep checking
          </button>
        </div>
      );
    }
    return (
      <GeneratingStripe label="Generating your lesson plan… checking again every 5s" />
    );
  }

  // READY (D-5) — render lp_content directly (NOT the stubbed LPViewer).
  if (!detail.lp_content) {
    return (
      <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-muted">
        The lesson plan is ready, but no content was returned.
      </div>
    );
  }

  return (
    <article
      className="prose prose-sm max-w-none text-dars-ink leading-relaxed"
      dangerouslySetInnerHTML={{ __html: detail.lp_content }}
    />
  );
}

function GeneratingStripe({ label }: { label: string }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-muted">
      <div className="flex items-center gap-3">
        <div className="h-2 w-2 rounded-full bg-dars-terra animate-pulse" />
        {label}
      </div>
    </div>
  );
}

function RetryButton({
  retrying,
  onClick,
}: {
  retrying: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={retrying}
      className="mt-3 px-3 py-1.5 rounded border border-dars-terra text-sm font-semibold text-dars-terra hover:bg-dars-terra/10 disabled:opacity-50"
    >
      {retrying ? "Retrying…" : "Retry"}
    </button>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
