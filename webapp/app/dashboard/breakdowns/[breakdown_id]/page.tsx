/**
 * F5.11 + F5.12 — Breakdown editor: per-chapter days + per-slot anchor.
 *
 * Day budget editing is allowed only on draft breakdowns; anchors only
 * on global/org draft scopes. Publishing happens via a button at top.
 */
"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  books as booksApi,
  breakdowns as breakdownsApi,
  curriculum as curriculumApi,
  DarsApiError,
  type BookChapter,
  type BreakdownDetail,
  type BreakdownSlot,
  type Grade,
  type Subject,
} from "@/lib/dars-api";

export default function BreakdownEditorPage() {
  const params = useParams<{ breakdown_id: string }>();
  const breakdownId = params.breakdown_id;

  const [data, setData] = useState<BreakdownDetail | null>(null);
  const [bookChaptersById, setBookChaptersById] = useState<Map<string, BookChapter>>(new Map());
  const [grades, setGrades] = useState<Grade[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [selectedSlot, setSelectedSlot] = useState<BreakdownSlot | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [bd, { items: gs }, { items: ss }] = await Promise.all([
        breakdownsApi.getBreakdown(breakdownId),
        curriculumApi.getGrades(),
        curriculumApi.getSubjects(),
      ]);
      setData(bd);
      setGrades(gs);
      setSubjects(ss);

      if (bd.book_id) {
        const { items: bcs } = await booksApi.getBookChapters(bd.book_id);
        setBookChaptersById(new Map(bcs.map((c) => [c.id, c])));
      }
    } catch (err) {
      setError(formatErr(err));
    }
  }, [breakdownId]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleSetChapterDays(chapterId: string, days: number) {
    if (!data) return;
    setBusy(true);
    try {
      await breakdownsApi.patchChapter(data.id, chapterId, { teaching_days: days });
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAnchorChange(slot: BreakdownSlot, value: string) {
    if (!data) return;
    setBusy(true);
    try {
      await breakdownsApi.patchSlotAnchor(data.id, slot.id, {
        anchor_date: value || null,
      });
      await load();
      // refresh selected
      const updated = data.slots.find((s) => s.id === slot.id);
      if (updated) setSelectedSlot(updated);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      await breakdownsApi.publish(data.id);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  const slotsByChapter = useMemo(() => {
    if (!data) return new Map<string, BreakdownSlot[]>();
    const out = new Map<string, BreakdownSlot[]>();
    for (const s of data.slots) {
      const arr = out.get(s.breakdown_chapter_id) ?? [];
      arr.push(s);
      out.set(s.breakdown_chapter_id, arr);
    }
    return out;
  }, [data]);

  const totalDays = useMemo(
    () => (data?.chapters ?? []).reduce((acc, c) => acc + c.teaching_days, 0),
    [data],
  );

  if (!data) return <p className="text-sm text-dars-muted">Loading…</p>;

  const editable = data.status === "draft";
  const anchorAllowed = editable && (data.scope === "global" || data.scope === "org");

  return (
    <div>
      <div className="text-xs text-dars-muted mb-2">
        <Link href="/dashboard/breakdowns" className="hover:text-dars-terra">← All breakdowns</Link>
      </div>

      <div className="flex items-start justify-between mb-4">
        <div>
          <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
            Breakdown
            <span className="text-base font-normal text-dars-muted ml-2">
              {grades.find((g) => g.id === data.grade_id)?.code ?? "—"} ·{" "}
              {subjects.find((s) => s.id === data.subject_id)?.code ?? "—"} ·{" "}
              {data.scope}
            </span>
          </h1>
          <p className="text-xs text-dars-muted mt-1">
            Status: <strong>{data.status}</strong>
            {data.total_teaching_days != null
              ? <>  ·  planned {data.total_teaching_days} teaching days  ·  current <strong>{totalDays}</strong></>
              : null}
          </p>
        </div>
        {data.status === "draft" ? (
          <button
            type="button"
            onClick={handlePublish}
            disabled={busy}
            className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "…" : "Publish"}
          </button>
        ) : null}
      </div>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      <div className="grid lg:grid-cols-[1fr_320px] gap-5">
        <ul className="space-y-3">
          {data.chapters.map((c) => {
            const book = bookChaptersById.get(c.book_chapter_id);
            const slots = slotsByChapter.get(c.id) ?? [];
            return (
              <li key={c.id} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid">
                <header className="p-3 border-b border-dars-rule-light flex items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-dars-ink">
                      Ch {c.position} · {book?.title ?? "—"}
                    </p>
                    <p className="text-[10px] text-dars-muted-light">
                      {slots.length} slot{slots.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <label className="text-xs text-dars-ink-soft">
                    Days{" "}
                    <input
                      type="number"
                      min={1}
                      defaultValue={c.teaching_days}
                      disabled={!editable || busy}
                      onBlur={(e) => {
                        const v = Number(e.target.value);
                        if (Number.isFinite(v) && v !== c.teaching_days) {
                          void handleSetChapterDays(c.id, v);
                        }
                      }}
                      className="w-16 px-2 py-1 rounded border border-dars-rule-light bg-white text-sm font-mono"
                    />
                  </label>
                </header>
                <SlotList
                  slots={slots}
                  selectedSlotId={selectedSlot?.id ?? null}
                  onSelect={setSelectedSlot}
                />
              </li>
            );
          })}
        </ul>

        <aside className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 h-fit sticky top-4">
          {selectedSlot ? (
            <>
              <h3 className="text-sm font-semibold text-dars-ink mb-2">
                Slot #{selectedSlot.position}
              </h3>
              <dl className="text-xs space-y-1 text-dars-ink-soft">
                <div className="flex justify-between">
                  <dt className="text-dars-muted">Type</dt>
                  <dd>{selectedSlot.slot_type}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-dars-muted">lp_type</dt>
                  <dd className="font-mono">{selectedSlot.lp_type ?? "—"}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-dars-muted">topic_id</dt>
                  <dd className="font-mono text-[10px]">
                    {selectedSlot.topic_id ? selectedSlot.topic_id.slice(0, 8) + "…" : "—"}
                  </dd>
                </div>
              </dl>

              <label className="block mt-3">
                <span className="text-xs text-dars-ink-soft">Anchor date</span>
                <input
                  type="date"
                  disabled={!anchorAllowed || busy}
                  defaultValue={selectedSlot.anchor_date ?? ""}
                  onBlur={(e) => {
                    if (e.target.value !== (selectedSlot.anchor_date ?? "")) {
                      void handleAnchorChange(selectedSlot, e.target.value);
                    }
                  }}
                  className="mt-1 w-full px-2 py-1 rounded border border-dars-rule-light bg-white text-sm font-mono"
                />
                {selectedSlot.anchor_date ? (
                  <button
                    type="button"
                    onClick={() => handleAnchorChange(selectedSlot, "")}
                    disabled={!anchorAllowed || busy}
                    className="text-[10px] text-dars-muted hover:text-dars-terra mt-1"
                  >
                    Clear anchor
                  </button>
                ) : null}
                {!anchorAllowed ? (
                  <p className="text-[10px] text-dars-muted-light mt-1">
                    Anchors are only editable on draft global/org breakdowns.
                  </p>
                ) : null}
              </label>
            </>
          ) : (
            <p className="text-xs text-dars-muted">Pick a slot to see details.</p>
          )}
        </aside>
      </div>
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

// ---------------------------------------------------------------------------
// SlotList — groups consecutive identical slots into "Days N–M" runs so a
// 180-slot breakdown is browsable. A "run" is a maximal sequence of slots
// with the same (slot_type, lp_type, topic_id) and no anchor on any slot
// in the middle. A run of length 1 renders as a single-day row.
// ---------------------------------------------------------------------------

interface SlotRun {
  slots: BreakdownSlot[];
  slot_type: string;
  lp_type: string | null;
  topic_id: string | null;
}

function groupSlotsIntoRuns(slots: BreakdownSlot[]): SlotRun[] {
  const runs: SlotRun[] = [];
  for (const s of slots) {
    const last = runs[runs.length - 1];
    const canMerge =
      last &&
      last.slot_type === s.slot_type &&
      last.lp_type === s.lp_type &&
      last.topic_id === s.topic_id &&
      // Anchors always break a run so the user can see them individually.
      !s.anchor_date &&
      !last.slots[last.slots.length - 1].anchor_date;
    if (canMerge) {
      last.slots.push(s);
    } else {
      runs.push({
        slots: [s],
        slot_type: s.slot_type,
        lp_type: s.lp_type,
        topic_id: s.topic_id,
      });
    }
  }
  return runs;
}

function SlotList({
  slots,
  selectedSlotId,
  onSelect,
}: {
  slots: BreakdownSlot[];
  selectedSlotId: string | null;
  onSelect: (s: BreakdownSlot) => void;
}) {
  const runs = useMemo(() => groupSlotsIntoRuns(slots), [slots]);
  const [expandedRunIdx, setExpandedRunIdx] = useState<number | null>(null);

  if (slots.length === 0) {
    return (
      <ul className="divide-y divide-dars-rule-light text-xs">
        <li className="px-3 py-2 text-dars-muted">No slots.</li>
      </ul>
    );
  }

  return (
    <ul className="divide-y divide-dars-rule-light text-xs">
      {runs.map((run, idx) => {
        const first = run.slots[0];
        const last = run.slots[run.slots.length - 1];
        const isRun = run.slots.length > 1;
        const expanded = expandedRunIdx === idx;
        const anyAnchor = run.slots.some((s) => s.anchor_date);

        if (!isRun) {
          // Single-day row — render the slot directly.
          return (
            <li
              key={first.id}
              className={
                "px-3 py-1.5 flex items-center gap-2 cursor-pointer hover:bg-dars-parchment-deep " +
                (selectedSlotId === first.id ? "bg-dars-parchment-deep" : "")
              }
              onClick={() => onSelect(first)}
            >
              <span className="font-mono text-dars-muted">#{first.position}</span>
              <span className="text-dars-ink">{first.slot_type}</span>
              {first.lp_type ? (
                <span className="text-[10px] text-dars-muted-light">{first.lp_type}</span>
              ) : null}
              {first.anchor_date ? (
                <span className="ml-auto text-[10px] text-dars-terra font-mono">
                  📌 {first.anchor_date}
                </span>
              ) : null}
            </li>
          );
        }

        return (
          <li key={`run-${idx}`}>
            <button
              type="button"
              onClick={() => setExpandedRunIdx(expanded ? null : idx)}
              className="w-full px-3 py-1.5 flex items-center gap-2 text-left hover:bg-dars-parchment-deep"
            >
              <span className="font-mono text-dars-muted">
                #{first.position}–{last.position}
              </span>
              <span className="text-dars-ink">{run.slot_type}</span>
              {run.lp_type ? (
                <span className="text-[10px] text-dars-muted-light">{run.lp_type}</span>
              ) : null}
              <span className="text-[10px] text-dars-muted ml-auto">
                {run.slots.length} day{run.slots.length === 1 ? "" : "s"}{" "}
                {expanded ? "▾" : "▸"}
              </span>
              {anyAnchor ? (
                <span className="text-[10px] text-dars-terra font-mono">📌</span>
              ) : null}
            </button>
            {expanded ? (
              <ul className="divide-y divide-dars-rule-light bg-dars-parchment">
                {run.slots.map((s) => (
                  <li
                    key={s.id}
                    className={
                      "pl-6 pr-3 py-1 flex items-center gap-2 cursor-pointer hover:bg-dars-parchment-deep " +
                      (selectedSlotId === s.id ? "bg-dars-parchment-deep" : "")
                    }
                    onClick={() => onSelect(s)}
                  >
                    <span className="font-mono text-dars-muted">#{s.position}</span>
                    <span className="text-[10px] text-dars-muted">{s.slot_type}</span>
                    {s.anchor_date ? (
                      <span className="ml-auto text-[10px] text-dars-terra font-mono">
                        📌 {s.anchor_date}
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
