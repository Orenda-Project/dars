/**
 * Polls a `generated_lps` row by id until the LP lands and renders the
 * content HTML. Used by /teacher-app/quick-lp where there's no class
 * slot to use slots.getLessonSlotDetail() against — instead we poll
 * the refresh endpoint directly.
 */
"use client";

import { useEffect, useRef, useState } from "react";

import { DarsApiError, generations } from "@/lib/dars-api";

interface LPContentViewerProps {
  generatedLPId: string;
}

const POLL_MS = 3000;
const MAX_POLLS = 80;

interface PollState {
  status: string;
  error_message?: string | null;
  content?: string | null;
}

export function LPContentViewer({ generatedLPId }: LPContentViewerProps) {
  const [state, setState] = useState<PollState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollCount = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    pollCount.current = 0;

    async function pump() {
      try {
        // refresh forces a status check; for cache-hit cases this is a noop
        const res = await generations.refreshLP(generatedLPId);
        if (cancelled) return;
        setState({ status: res.status });

        if (res.status === "READY" || res.status === "ERROR") return;
        if (pollCount.current < MAX_POLLS) {
          pollCount.current += 1;
          timer = setTimeout(pump, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        setError(formatErr(err));
      }
    }

    pump();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [generatedLPId]);

  if (error) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm">
        <p className="font-semibold text-dars-ink">Failed to load LP.</p>
        <p className="text-xs text-dars-muted mt-1">{error}</p>
      </div>
    );
  }
  if (!state) return <Pulse label="Submitting…" />;
  if (state.status === "READY") {
    // We don't have a GET /generated-lps/{id} that returns content;
    // refresh's return shape gives status only. So once ready, prompt
    // the user to look at the new entry via the dashboard / class
    // detail. (A future Phase 5 endpoint surfaces content directly.)
    return (
      <div className="rounded-md border border-emerald-300 bg-emerald-50 p-4 text-sm text-dars-ink">
        <p className="font-semibold">LP generated.</p>
        <p className="text-xs text-dars-muted mt-1 break-all">
          Row id: <code className="font-mono">{generatedLPId}</code>.
        </p>
        <p className="text-xs text-dars-muted-light mt-2">
          A read endpoint for one-off LP content lands in Phase 5; for now
          the LP is stored under this id and can be retrieved via the
          dashboard.
        </p>
      </div>
    );
  }
  if (state.status === "ERROR") {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <p className="font-semibold">LP generation failed.</p>
        <p className="text-xs text-dars-muted mt-1">
          {state.error_message ?? "Upstream service reported an error."}
        </p>
      </div>
    );
  }
  return <Pulse label={`Generating (status=${state.status})…`} />;
}

function Pulse({ label }: { label: string }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-muted flex items-center gap-3">
      <span className="h-2 w-2 rounded-full bg-dars-terra animate-pulse" />
      {label}
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
