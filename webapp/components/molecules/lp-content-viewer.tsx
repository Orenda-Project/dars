/**
 * Quick-LP result viewer. Originally polled the LP row until terminal
 * and showed the content; while we iterate on the slot model the
 * backend may not actually generate a body, so we just show the canned
 * stub from lib/lp-stub.ts after the user submits.
 */
"use client";

import { STUB_LP_HTML } from "@/lib/lp-stub";

interface LPContentViewerProps {
  generatedLPId: string;
}

export function LPContentViewer({ generatedLPId }: LPContentViewerProps) {
  return (
    <div className="space-y-3">
      <div className="rounded-md border border-emerald-300 bg-emerald-50 p-3 text-xs text-dars-ink">
        <p className="font-semibold">Sample lesson plan</p>
        <p className="text-dars-muted mt-1 break-all">
          Row id: <code className="font-mono">{generatedLPId}</code>
        </p>
      </div>
      <article
        className="prose prose-sm max-w-none text-dars-ink leading-relaxed"
        dangerouslySetInnerHTML={{ __html: STUB_LP_HTML }}
      />
    </div>
  );
}
