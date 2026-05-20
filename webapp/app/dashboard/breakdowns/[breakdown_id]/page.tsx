/**
 * Breakdown editor — chapter days, anchor placement, and per-slot editing.
 *
 * - Day budget editing: draft breakdowns only.
 * - Anchor placement: draft global/org breakdowns only (D-7 of the v2 rebuild).
 * - Slot editing (slot_type, lp_type, topic_id) + add/delete: draft + org-scope
 *   only. See docs/features/breakdown-slot-editing/.
 * - Publish: explicit button at top.
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
  type BreakdownChapter,
  type BreakdownDetail,
  type BreakdownSlot,
  type Grade,
  type Subject,
  type Topic,
} from "@/lib/dars-api";
import {
  buildSlotCombos,
  comboValueFromSlot,
  defaultComboForNewSlot,
  parseComboValue,
  type SlotCombo,
} from "@/lib/slot-types";

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
  const [topicsByBookChapter, setTopicsByBookChapter] = useState<Map<string, Topic[]>>(new Map());

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

  const subjectCode = useMemo(() => {
    if (!data) return "";
    return subjects.find((s) => s.id === data.subject_id)?.code ?? "";
  }, [data, subjects]);

  const breakdownChaptersById = useMemo<Map<string, BreakdownChapter>>(
    () => new Map((data?.chapters ?? []).map((c) => [c.id, c])),
    [data],
  );

  const ensureTopicsForBookChapter = useCallback(
    async (bookChapterId: string): Promise<Topic[]> => {
      const cached = topicsByBookChapter.get(bookChapterId);
      if (cached) return cached;
      const { items } = await booksApi.getTopics(bookChapterId);
      setTopicsByBookChapter((prev) => {
        const next = new Map(prev);
        next.set(bookChapterId, items);
        return next;
      });
      return items;
    },
    [topicsByBookChapter],
  );

  // Whenever the selected slot changes, prefetch its chapter's topics so the
  // dropdown is populated when the user opens it.
  useEffect(() => {
    if (!selectedSlot || !data) return;
    const bch = breakdownChaptersById.get(selectedSlot.breakdown_chapter_id);
    if (!bch) return;
    void ensureTopicsForBookChapter(bch.book_chapter_id);
  }, [selectedSlot, data, breakdownChaptersById, ensureTopicsForBookChapter]);

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

  async function handleSaveSlot(
    slot: BreakdownSlot,
    patch: { slot_type?: BreakdownSlot["slot_type"]; lp_type?: string | null; topic_id?: string | null },
  ) {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await breakdownsApi.patchSlot(data.id, slot.id, patch);
      await load();
      setSelectedSlot(updated);
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteSlot(slot: BreakdownSlot) {
    if (!data) return;
    if (!window.confirm(`Delete slot #${slot.position}? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      await breakdownsApi.deleteSlot(data.id, slot.id);
      setSelectedSlot(null);
      await load();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAddSlot(chapter: BreakdownChapter) {
    if (!data) return;
    setBusy(true);
    setError(null);
    try {
      const combo = defaultComboForNewSlot(subjectCode);
      const allSlots = data.slots;
      const chapterSlots = allSlots.filter((s) => s.breakdown_chapter_id === chapter.id);
      const nextPosition = allSlots.reduce((acc, s) => Math.max(acc, s.position), 0) + 1;
      const nextChapterPosition =
        chapterSlots.reduce((acc, s) => Math.max(acc, s.chapter_position), 0) + 1;
      const created = await breakdownsApi.addSlot(data.id, {
        breakdown_chapter_id: chapter.id,
        position: nextPosition,
        chapter_position: nextChapterPosition,
        slot_type: combo.slot_type,
        lp_type: combo.lp_type,
        topic_id: null,
        anchor_date: null,
      });
      await load();
      setSelectedSlot(created);
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
  const slotEditAllowed = editable && data.scope === "org";

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
              {subjectCode || "—"} ·{" "}
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
                  <div className="flex items-center gap-2">
                    {slotEditAllowed ? (
                      <button
                        type="button"
                        onClick={() => handleAddSlot(c)}
                        disabled={busy}
                        className="text-xs px-2 py-1 rounded border border-dars-rule-light text-dars-ink hover:bg-dars-parchment-deep disabled:opacity-50"
                      >
                        + Add slot
                      </button>
                    ) : null}
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
                  </div>
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
            slotEditAllowed ? (
              <SlotEditor
                key={selectedSlot.id}
                slot={selectedSlot}
                subjectCode={subjectCode}
                bookChapterId={
                  breakdownChaptersById.get(selectedSlot.breakdown_chapter_id)?.book_chapter_id ?? null
                }
                topicsByBookChapter={topicsByBookChapter}
                anchorAllowed={anchorAllowed}
                busy={busy}
                onSave={(patch) => handleSaveSlot(selectedSlot, patch)}
                onDelete={() => handleDeleteSlot(selectedSlot)}
                onAnchorChange={(value) => handleAnchorChange(selectedSlot, value)}
              />
            ) : (
              <SlotReadOnly
                slot={selectedSlot}
                anchorAllowed={anchorAllowed}
                busy={busy}
                onAnchorChange={(value) => handleAnchorChange(selectedSlot, value)}
              />
            )
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
// SlotEditor — combined slot_type/lp_type dropdown, topic dropdown (scoped to
// the slot's chapter), anchor, Save/Cancel, Delete. Atomic PATCH on save
// (D-2). Topic disabled for assessment slots (D-3 + phase doc).
// ---------------------------------------------------------------------------

interface SlotEditorProps {
  slot: BreakdownSlot;
  subjectCode: string;
  bookChapterId: string | null;
  topicsByBookChapter: Map<string, Topic[]>;
  anchorAllowed: boolean;
  busy: boolean;
  onSave: (patch: {
    slot_type?: BreakdownSlot["slot_type"];
    lp_type?: string | null;
    topic_id?: string | null;
  }) => Promise<void>;
  onDelete: () => Promise<void>;
  onAnchorChange: (value: string) => void;
}

function SlotEditor({
  slot,
  subjectCode,
  bookChapterId,
  topicsByBookChapter,
  anchorAllowed,
  busy,
  onSave,
  onDelete,
  onAnchorChange,
}: SlotEditorProps) {
  const combos = useMemo<SlotCombo[]>(
    () => buildSlotCombos(subjectCode),
    [subjectCode],
  );
  const currentCombo = comboValueFromSlot(slot);

  const [comboValue, setComboValue] = useState<string>(currentCombo);
  const [topicId, setTopicId] = useState<string | null>(slot.topic_id);

  const parsed = useMemo(() => parseComboValue(comboValue), [comboValue]);
  const isAssessment =
    parsed.slot_type === "formative_assessment" || parsed.slot_type === "summative_assessment";

  const topics = bookChapterId ? topicsByBookChapter.get(bookChapterId) ?? [] : [];

  const comboDirty = comboValue !== currentCombo;
  const topicDirty = topicId !== slot.topic_id;
  const dirty = comboDirty || topicDirty;

  function buildPatch() {
    const patch: {
      slot_type?: BreakdownSlot["slot_type"];
      lp_type?: string | null;
      topic_id?: string | null;
    } = {};
    if (comboDirty) {
      patch.slot_type = parsed.slot_type;
      patch.lp_type = parsed.lp_type;
    }
    if (topicDirty) {
      patch.topic_id = topicId;
    }
    return patch;
  }

  function handleCancel() {
    setComboValue(currentCombo);
    setTopicId(slot.topic_id);
  }

  return (
    <>
      <h3 className="text-sm font-semibold text-dars-ink mb-3">
        Slot #{slot.position}
      </h3>

      <label className="block mb-3">
        <span className="text-xs text-dars-ink-soft">Type</span>
        <select
          value={comboValue}
          disabled={busy}
          onChange={(e) => setComboValue(e.target.value)}
          className="mt-1 w-full px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
        >
          {combos.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block mb-3">
        <span className="text-xs text-dars-ink-soft">Topic</span>
        <select
          value={topicId ?? ""}
          disabled={busy || isAssessment || topics.length === 0}
          onChange={(e) => setTopicId(e.target.value === "" ? null : e.target.value)}
          className="mt-1 w-full px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
        >
          <option value="">— none —</option>
          {topics.map((t) => (
            <option key={t.id} value={t.id}>
              Topic {t.topic_number} — {truncate(t.title, 40)}
            </option>
          ))}
        </select>
        {isAssessment ? (
          <p className="text-[10px] text-dars-muted-light mt-1">
            Assessment slots cover multiple topics — editing the topic set is a follow-up.
          </p>
        ) : topics.length === 0 ? (
          <p className="text-[10px] text-dars-muted-light mt-1">Loading topics…</p>
        ) : null}
      </label>

      <label className="block mb-3">
        <span className="text-xs text-dars-ink-soft">Anchor date</span>
        <input
          type="date"
          disabled={!anchorAllowed || busy}
          defaultValue={slot.anchor_date ?? ""}
          onBlur={(e) => {
            if (e.target.value !== (slot.anchor_date ?? "")) {
              onAnchorChange(e.target.value);
            }
          }}
          className="mt-1 w-full px-2 py-1 rounded border border-dars-rule-light bg-white text-sm font-mono"
        />
        {slot.anchor_date ? (
          <button
            type="button"
            onClick={() => onAnchorChange("")}
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

      <div className="flex items-center gap-2 mt-4">
        <button
          type="button"
          disabled={!dirty || busy}
          onClick={() => void onSave(buildPatch())}
          className="px-3 py-1 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
        >
          Save
        </button>
        <button
          type="button"
          disabled={!dirty || busy}
          onClick={handleCancel}
          className="px-3 py-1 rounded border border-dars-rule-light text-dars-ink text-xs hover:bg-dars-parchment-deep disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void onDelete()}
          className="ml-auto text-[10px] text-dars-terra hover:underline disabled:opacity-50"
        >
          Delete
        </button>
      </div>
    </>
  );
}

// Read-only side panel for non-editable breakdowns (published, class scope).
function SlotReadOnly({
  slot,
  anchorAllowed,
  busy,
  onAnchorChange,
}: {
  slot: BreakdownSlot;
  anchorAllowed: boolean;
  busy: boolean;
  onAnchorChange: (value: string) => void;
}) {
  return (
    <>
      <h3 className="text-sm font-semibold text-dars-ink mb-2">
        Slot #{slot.position}
      </h3>
      <dl className="text-xs space-y-1 text-dars-ink-soft">
        <div className="flex justify-between">
          <dt className="text-dars-muted">Type</dt>
          <dd>{slot.slot_type}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-dars-muted">lp_type</dt>
          <dd className="font-mono">{slot.lp_type ?? "—"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-dars-muted">topic_id</dt>
          <dd className="font-mono text-[10px]">
            {slot.topic_id ? slot.topic_id.slice(0, 8) + "…" : "—"}
          </dd>
        </div>
      </dl>

      <label className="block mt-3">
        <span className="text-xs text-dars-ink-soft">Anchor date</span>
        <input
          type="date"
          disabled={!anchorAllowed || busy}
          defaultValue={slot.anchor_date ?? ""}
          onBlur={(e) => {
            if (e.target.value !== (slot.anchor_date ?? "")) {
              onAnchorChange(e.target.value);
            }
          }}
          className="mt-1 w-full px-2 py-1 rounded border border-dars-rule-light bg-white text-sm font-mono"
        />
        {slot.anchor_date ? (
          <button
            type="button"
            onClick={() => onAnchorChange("")}
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
  );
}

function truncate(s: string, n: number): string {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
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
