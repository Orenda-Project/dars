/**
 * Core Book Import (core-book-import Phase 2, D-10).
 *
 * Admin browses importable taleemabad-core books, picks one, confirms the
 * derived scope + curriculum, and starts a background import. A poller shows
 * live per-step progress and a final results card; recent runs are listed.
 *
 * Backend: /api/v2/admin/core-books + /admin/book-imports (F-1.3, F-1.5).
 * Imports 503 until the core-DB + ANTHROPIC_API_KEY env vars are set (D-7).
 */
"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  admin,
  bookImport,
  DarsApiError,
  IMPORT_STEPS,
  type AdminMeResponse,
  type CoreBook,
  type ImportRun,
} from "@/lib/dars-api";

export default function AdminBooksPage() {
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [books, setBooks] = useState<CoreBook[] | null>(null);
  const [schema, setSchema] = useState("fde_staging");
  const [bookIdInput, setBookIdInput] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<CoreBook | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [run, setRun] = useState<ImportRun | null>(null);
  const [recent, setRecent] = useState<ImportRun[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [starting, setStarting] = useState(false);

  // Look up core books — only fires on explicit submit (no auto-fetch on load).
  // Needs at least a book ID or a search term; schema scopes the source.
  const lookUp = useCallback(async () => {
    const id = bookIdInput.trim();
    const parsedId = id ? Number(id) : undefined;
    if (id && (parsedId === undefined || !Number.isInteger(parsedId) || parsedId <= 0)) {
      setError("Book ID must be a positive integer.");
      return;
    }
    setError(null);
    setSelected(null);
    setLoading(true);
    try {
      const { items } = await bookImport.getCoreBooks({
        book_id: parsedId,
        search: parsedId ? undefined : search.trim() || undefined,
        schema: schema.trim() || undefined,
      });
      setBooks(items);
      if (items.length === 1) setSelected(items[0]);
    } catch (err) {
      setBooks([]);
      setError(formatErr(err));
    } finally {
      setLoading(false);
    }
  }, [bookIdInput, search, schema]);

  // On mount: who am I + recent runs ONLY. The core-book list waits for Look up.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const m = await admin.me();
        if (!cancelled) setMe(m);
      } catch {
        /* me() failure is non-fatal */
      }
      try {
        const { items } = await bookImport.getRuns();
        if (!cancelled) setRecent(items);
      } catch {
        /* recent runs are best-effort */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Poll the active run while it's pending/running.
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    async function tick() {
      try {
        const r = await bookImport.getRun(runId as string);
        if (cancelled) return;
        setRun(r);
        if (r.status === "pending" || r.status === "running") {
          pollRef.current = setTimeout(tick, 2000);
        } else {
          // terminal — refresh the recent list once.
          bookImport.getRuns().then(({ items }) => !cancelled && setRecent(items)).catch(() => {});
        }
      } catch (err) {
        if (!cancelled) setError(formatErr(err));
      }
    }
    tick();
    return () => {
      cancelled = true;
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, [runId]);

  async function startImport() {
    if (!selected) return;
    setStarting(true);
    setError(null);
    try {
      const { import_run_id } = await bookImport.start({
        core_book_id: selected.core_book_id,
        curriculum_id: me?.curriculum_id,
        schema_name: schema.trim() || undefined,
      });
      setRun(null);
      setRunId(import_run_id);
      setSelected(null);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setStarting(false);
    }
  }

  const busy = run?.status === "pending" || run?.status === "running";

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-1">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
          Import a book
        </h1>
        <Link
          href="/dashboard/admin/books/all"
          className="text-sm text-dars-terra hover:underline shrink-0"
        >
          View all books →
        </Link>
      </div>
      <p className="text-sm text-dars-muted mb-4">
        Bring a book in from taleemabad-core — its SLOs, sub-SLOs, chapters, and topics —
        into Dars{me ? <> under <code className="font-mono">{me.curriculum_code}</code></> : null}.
      </p>

      {error ? (
        <p className="text-sm text-dars-terra mb-3 rounded border border-dars-terra/30 bg-dars-terra/5 px-3 py-2">
          {error}
        </p>
      ) : null}

      {/* Active / last run */}
      {run ? <RunPanel run={run} onDismiss={busy ? undefined : () => { setRun(null); setRunId(null); }} /> : null}

      {/* Source + lookup — nothing is fetched until the admin clicks Look up */}
      {!busy ? (
        <section className="mt-4">
          <form
            onSubmit={(e) => { e.preventDefault(); lookUp(); }}
            className="rounded border border-dars-rule-light bg-dars-parchment-mid p-3 mb-3 space-y-2"
          >
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <label className="block">
                <span className="text-[10px] uppercase tracking-wide text-dars-muted-light">Source schema</span>
                <input
                  value={schema}
                  onChange={(e) => setSchema(e.target.value)}
                  placeholder="fde_staging"
                  className="mt-0.5 w-full px-3 py-1.5 rounded border border-dars-rule-light bg-white text-sm font-mono"
                />
              </label>
              <label className="block">
                <span className="text-[10px] uppercase tracking-wide text-dars-muted-light">Core book ID</span>
                <input
                  value={bookIdInput}
                  onChange={(e) => setBookIdInput(e.target.value)}
                  inputMode="numeric"
                  placeholder="e.g. 1171"
                  className="mt-0.5 w-full px-3 py-1.5 rounded border border-dars-rule-light bg-white text-sm font-mono"
                />
              </label>
            </div>
            <div className="flex items-center gap-2">
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="…or search by title (ignored if an ID is given)"
                disabled={!!bookIdInput.trim()}
                className="flex-1 px-3 py-1.5 rounded border border-dars-rule-light bg-white text-sm disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={loading || (!bookIdInput.trim() && !search.trim())}
                className="px-4 py-1.5 rounded bg-dars-ink text-white text-sm font-medium hover:opacity-90 disabled:opacity-40"
              >
                {loading ? "Looking up…" : "Look up"}
              </button>
            </div>
            <p className="text-[11px] text-dars-muted-light">
              Enter a book ID for an exact match, or a title to search. Nothing is fetched until you look up.
            </p>
          </form>

          {books === null ? (
            <p className="text-sm text-dars-muted-light">Enter a book ID or title above and click Look up.</p>
          ) : books.length === 0 ? (
            <p className="text-sm text-dars-muted">No matching books in <code className="font-mono">{schema}</code>.</p>
          ) : (
            <ul className="space-y-1.5">
              {books.map((b) => {
                const isSel = selected?.core_book_id === b.core_book_id;
                return (
                  <li key={b.core_book_id}>
                    <button
                      type="button"
                      onClick={() => setSelected(isSel ? null : b)}
                      className={
                        "w-full text-left rounded border p-3 transition-colors " +
                        (isSel
                          ? "border-dars-terra bg-dars-terra/5"
                          : "border-dars-rule-light bg-dars-parchment-mid hover:bg-dars-parchment-deep")
                      }
                    >
                      <div className="flex items-center gap-2">
                        <span className="flex-1 text-sm font-medium text-dars-ink">{b.title}</span>
                        {b.already_imported ? (
                          <span className="text-[10px] uppercase tracking-wide rounded px-1.5 py-0.5 bg-dars-ink/5 text-dars-muted">
                            Imported
                          </span>
                        ) : null}
                        <span className="text-[10px] font-mono text-dars-muted-light">#{b.core_book_id}</span>
                      </div>
                      <p className="text-[11px] text-dars-muted-light mt-0.5">
                        {[b.grade, b.subject, b.publisher, b.total_chapters != null ? `${b.total_chapters} ch` : null]
                          .filter(Boolean)
                          .join(" · ")}
                      </p>
                    </button>

                    {isSel ? (
                      <div className="mt-1.5 rounded border border-dars-rule-light bg-white p-3">
                        <p className="text-xs text-dars-muted mb-2">
                          Import <span className="text-dars-ink font-medium">{b.title}</span> as{" "}
                          <code className="font-mono">{b.grade ?? "?"}</code> ·{" "}
                          <code className="font-mono">{b.subject ?? "?"}</code> ·{" "}
                          <code className="font-mono">{me?.curriculum_code ?? "curriculum"}</code>
                          {b.already_imported ? " (re-import will update existing rows)" : null}.
                        </p>
                        <button
                          type="button"
                          disabled={starting}
                          onClick={startImport}
                          className="px-3 py-1.5 rounded bg-dars-terra text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
                        >
                          {starting ? "Starting…" : "Import"}
                        </button>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>
      ) : null}

      {/* Recent imports */}
      {recent.length > 0 ? (
        <details className="mt-6">
          <summary className="cursor-pointer select-none text-sm text-dars-muted hover:text-dars-ink">
            Recent imports ({recent.length})
          </summary>
          <ul className="mt-2 space-y-1 text-xs">
            {recent.map((r) => (
              <li
                key={r.id}
                className="flex items-center gap-2 rounded border border-dars-rule-light bg-dars-parchment-mid px-3 py-1.5"
              >
                <StatusDot status={r.status} />
                <span className="font-mono text-dars-muted-light">#{r.core_book_id}</span>
                <span className="text-dars-ink-soft flex-1 truncate">{r.status}</span>
                {r.dars_book_id ? (
                  <Link
                    href={`/dashboard/curriculum/books/${r.dars_book_id}`}
                    className="text-dars-terra hover:underline shrink-0"
                  >
                    View book
                  </Link>
                ) : null}
                <button
                  type="button"
                  onClick={() => { setRunId(r.id); setRun(r); }}
                  className="text-dars-muted hover:text-dars-ink shrink-0"
                >
                  Details
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function RunPanel({ run, onDismiss }: { run: ImportRun; onDismiss?: () => void }) {
  const busy = run.status === "pending" || run.status === "running";
  return (
    <section className="rounded border border-dars-rule-light bg-dars-parchment-mid p-4">
      <div className="flex items-center gap-2 mb-3">
        <StatusDot status={run.status} />
        <span className="text-sm font-medium text-dars-ink">
          Import #{run.core_book_id} — {run.status}
          {run.current_step ? <span className="text-dars-muted"> · {run.current_step}</span> : null}
        </span>
        {onDismiss ? (
          <button
            type="button"
            onClick={onDismiss}
            className="ml-auto text-xs text-dars-muted hover:text-dars-ink"
          >
            Dismiss
          </button>
        ) : null}
      </div>

      {/* Per-step checklist */}
      <ol className="space-y-1 text-xs">
        {IMPORT_STEPS.map((step) => {
          const s = run.steps?.[step];
          const status = (s?.status as string) || "pending";
          const count = s?.count;
          return (
            <li key={step} className="flex items-center gap-2">
              <span className="w-4 text-center">
                {status === "done" ? "✓" : status === "running" ? "…" : "·"}
              </span>
              <span className={status === "done" ? "text-dars-ink" : "text-dars-muted"}>
                {STEP_LABELS[step]}
              </span>
              {count != null ? <span className="text-dars-muted-light">({count})</span> : null}
            </li>
          );
        })}
      </ol>

      {busy ? <p className="text-[11px] text-dars-muted-light mt-2">Running… this can take a few minutes.</p> : null}

      {run.status === "succeeded" ? (
        <div className="mt-3 border-t border-dars-rule-light pt-3">
          <p className="text-sm text-dars-ink mb-1">Imported.</p>
          <p className="text-xs text-dars-muted">
            {Object.entries(run.counts || {})
              .map(([k, v]) => `${k}: ${v}`)
              .join(" · ") || "no counts reported"}
          </p>
          {run.dars_book_id ? (
            <Link
              href={`/dashboard/curriculum/books/${run.dars_book_id}`}
              className="inline-block mt-2 text-sm text-dars-terra hover:underline"
            >
              View the imported book →
            </Link>
          ) : null}
        </div>
      ) : null}

      {run.status === "failed" ? (
        <div className="mt-3 border-t border-dars-rule-light pt-3">
          <p className="text-sm text-dars-terra">
            Failed{run.current_step ? ` at ${run.current_step}` : ""}.
          </p>
          {run.error ? <p className="text-[11px] text-dars-muted mt-1 font-mono break-words">{run.error}</p> : null}
        </div>
      ) : null}

      {run.warnings && run.warnings.length > 0 ? (
        <details className="mt-3 border-t border-dars-rule-light pt-2">
          <summary className="cursor-pointer text-[11px] text-dars-muted-light">
            {run.warnings.length} warning{run.warnings.length === 1 ? "" : "s"}
          </summary>
          <ul className="mt-1 space-y-0.5 text-[11px] text-dars-muted-light list-disc pl-4">
            {run.warnings.map((w, i) => <li key={i}>{String(w)}</li>)}
          </ul>
        </details>
      ) : null}
    </section>
  );
}

const STEP_LABELS: Record<string, string> = {
  slos: "SLOs",
  sub_slos: "Sub-SLOs (LLM breakdown)",
  book_chapters: "Book + chapters",
  topics: "Topics",
  mappings: "Topic / chapter mappings",
};

function StatusDot({ status }: { status: string }) {
  const color =
    status === "succeeded" ? "bg-green-600"
    : status === "failed" ? "bg-dars-terra"
    : status === "running" || status === "pending" ? "bg-amber-500"
    : "bg-dars-muted-light";
  return <span className={`inline-block h-2 w-2 rounded-full ${color}`} aria-label={status} />;
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    if (err.status === 503) {
      return "taleemabad-core is not configured on this server yet — set CORE_DB_URL + ANTHROPIC_API_KEY to enable imports.";
    }
    if (err.status === 409) return "An import is already running — wait for it to finish.";
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
