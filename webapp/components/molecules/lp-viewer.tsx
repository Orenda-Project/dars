/**
 * F4.4 — LP viewer.
 *
 * Polls slots.getLessonSlotDetail() until LP status is terminal, then
 * renders the HTML in a styled container. Handles all three terminal
 * states (READY, ERROR, not_generated) and the in-flight loading.
 */
"use client";

import { useEffect, useRef, useState } from "react";

import {
  curriculum as curriculumApi,
  slots,
  type ClassLessonSlotDetail,
  type SubSLO,
  DarsApiError,
} from "@/lib/dars-api";

interface LPViewerProps {
  slotId: string;
}

const POLL_MS = 3000;
const MAX_POLLS = 80; // ~4 minutes ceiling

export function LPViewer({ slotId }: LPViewerProps) {
  const [detail, setDetail] = useState<ClassLessonSlotDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollCount = useRef(0);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    pollCount.current = 0;

    async function pump() {
      try {
        const next = await slots.getLessonSlotDetail(slotId);
        if (cancelled) return;
        setDetail(next);
        setError(null);

        const inflight =
          next.lp_status === "PENDING" || next.lp_status === "IN_FLIGHT";
        if (inflight && pollCount.current < MAX_POLLS) {
          pollCount.current += 1;
          timer = setTimeout(pump, POLL_MS);
        }
      } catch (err) {
        if (cancelled) return;
        const msg =
          err instanceof DarsApiError
            ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
            : err instanceof Error
            ? err.message
            : "Failed to load LP";
        setError(msg);
      }
    }

    pump();

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [slotId]);

  if (error) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <strong className="font-semibold">Couldn’t load LP.</strong>
        <p className="text-dars-muted mt-1">{error}</p>
      </div>
    );
  }

  if (!detail) {
    return <LoadingStripe label="Loading lesson plan…" />;
  }

  if (detail.lp_status === "not_generated") {
    return (
      <EmptyHint
        title="No LP yet"
        body="This slot hasn’t been generated. Generation is admin-triggered when a breakdown is published."
      />
    );
  }

  if (detail.lp_status === "PENDING" || detail.lp_status === "IN_FLIGHT") {
    return (
      <LoadingStripe label="Generating lesson plan (this can take 1–2 minutes)…" />
    );
  }

  if (detail.lp_status === "ERROR") {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 text-sm text-dars-ink">
        <strong className="font-semibold">LP unavailable.</strong>
        <p className="text-dars-muted mt-1">
          {detail.lp_error_message ??
            "Generation failed. Contact your admin to retry. You can still mark this lesson as taught."}
        </p>
      </div>
    );
  }

  // READY
  return (
    <div className="space-y-4">
      <CoveredSLOs
        subSloIds={detail.lp_covered_sub_slo_ids}
        taggingStatus={detail.lp_tagging_status}
      />
      <article
        className="prose prose-sm max-w-none text-dars-ink leading-relaxed"
        // The HTML comes from LP Assistant; we trust the source (it's our
        // own service). XSS risk is bounded by the dars→LP Assistant trust
        // boundary already enforced via api-key + webhook secret.
        dangerouslySetInnerHTML={{ __html: detail.lp_content ?? "" }}
      />
    </div>
  );
}

function CoveredSLOs({
  subSloIds,
  taggingStatus,
}: {
  subSloIds: string[];
  taggingStatus: ClassLessonSlotDetail["lp_tagging_status"];
}) {
  const [subSlos, setSubSlos] = useState<SubSLO[] | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  // Stabilise array identity across poll cycles so we don't refetch on
  // every parent re-render.
  const idKey = subSloIds.join(",");

  useEffect(() => {
    let cancelled = false;
    const ids = idKey ? idKey.split(",") : [];
    if (ids.length === 0) {
      setSubSlos([]);
      return;
    }
    (async () => {
      try {
        const fetched = await Promise.all(
          ids.map((id) => curriculumApi.getSubSLO(id)),
        );
        if (!cancelled) setSubSlos(fetched);
      } catch {
        if (!cancelled) setSubSlos([]); // fail soft — chips disappear
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [idKey]);

  // Hide entirely if the LP is past tagging and no SLOs were tagged.
  if (taggingStatus === "done" && subSloIds.length === 0) return null;

  return (
    <section className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3">
      <p className="text-[10px] uppercase tracking-wider text-dars-muted font-semibold mb-2">
        Covered SLOs
      </p>
      {taggingStatus === "pending" ? (
        <p className="text-xs text-dars-muted italic">SLO tags pending…</p>
      ) : taggingStatus === "failed" ? (
        <p className="text-xs text-dars-muted italic">SLO tagging failed.</p>
      ) : subSlos === null ? (
        <p className="text-xs text-dars-muted italic">Loading…</p>
      ) : subSlos.length === 0 ? (
        <p className="text-xs text-dars-muted italic">No SLOs tagged.</p>
      ) : (
        <ul className="flex flex-wrap gap-1.5">
          {subSlos.map((s) => {
            const isOpen = expanded === s.id;
            return (
              <li key={s.id} className="w-full">
                <button
                  type="button"
                  onClick={() => setExpanded(isOpen ? null : s.id)}
                  className="text-left text-xs font-mono px-2 py-1 rounded bg-dars-parchment border border-dars-rule-light hover:bg-dars-parchment-deep transition-colors"
                >
                  {s.code}
                  <span className="ml-1 text-dars-muted">{isOpen ? "▾" : "▸"}</span>
                </button>
                {isOpen ? (
                  <p className="mt-1 text-xs text-dars-ink-soft pl-2 border-l-2 border-dars-terra/40">
                    {s.statement}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
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

function EmptyHint({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4">
      <p className="text-sm font-medium text-dars-ink">{title}</p>
      <p className="text-xs text-dars-muted mt-1">{body}</p>
    </div>
  );
}
