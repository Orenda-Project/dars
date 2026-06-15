/**
 * dynamic-chapter-planner F-3.3 — Reteach suggestion panel (teacher-app).
 *
 * Surfaces AFTER a formative assessment is graded, ONLY when the class fell
 * below the mastery threshold on one or more sub-SLOs. For each below-threshold
 * sub-SLO the teacher explicitly confirms a reteach mode before anything is
 * applied — reteach NEVER auto-applies (D-9). Two modes are offered, with
 * lightweight as the recommended default:
 *
 *   - lightweight — re-cover the sub-SLO in the next class (flips coverage to
 *     needs-rework). No new slot, no schedule shift.
 *   - heavy — add a reteach lesson. Consumes a spare revision day if one is
 *     available downstream (schedule unchanged), otherwise inserts a new day,
 *     which can push later slots past the end of the school year. When that
 *     happens we show the overflow consequence in plain language.
 *
 * Pure presentation: the page owns the suggestion data, the per-sub-SLO state
 * machine, the API calls, and busy/error state, and passes them in as props
 * (mirrors mastery-entry-template). No hooks, no fetch, no routing here.
 */
"use client";

import type {
  OverflowConsequence,
  ReteachActionResponse,
  ReteachSuggestionItem,
} from "@/lib/dars-api";

export type ReteachMode = "lightweight" | "heavy";

/** Per-sub-SLO outcome once the teacher has acted (or declined). */
export interface ReteachItemState {
  /** Selected mode in the confirm step (lightweight recommended). */
  mode: ReteachMode;
  /** True while the confirmReteach call for this sub-SLO is in flight. */
  busy: boolean;
  /** The applied result, once confirmed. Drives the outcome message. */
  result: ReteachActionResponse | null;
  /** Per-item error from a failed confirm. */
  error: string | null;
  /** True after the teacher dismissed/declined this suggestion. */
  declined: boolean;
}

export function emptyReteachItemState(): ReteachItemState {
  return { mode: "lightweight", busy: false, result: null, error: null, declined: false };
}

interface ReteachPanelProps {
  /** Mastery threshold (percent) the items fell below. */
  threshold: number;
  /** Below-threshold sub-SLOs surfaced for this graded FA slot. */
  items: ReteachSuggestionItem[];
  /** Per-sub-SLO UI/outcome state, keyed by sub_slo_id. */
  states: Record<string, ReteachItemState>;
  /** Teacher picked a mode for a sub-SLO (before confirming). */
  onSelectMode: (subSloId: string, mode: ReteachMode) => void;
  /** Teacher confirmed the reteach for a sub-SLO with the selected mode. */
  onConfirm: (subSloId: string) => void;
  /** Teacher dismissed the suggestion for a sub-SLO (leaves the plan untouched). */
  onDecline: (subSloId: string) => void;
}

export function ReteachPanel({
  threshold,
  items,
  states,
  onSelectMode,
  onConfirm,
  onDecline,
}: ReteachPanelProps) {
  if (items.length === 0) return null;

  // Items the teacher still has to deal with (not yet acted on or declined).
  const openCount = items.filter((it) => {
    const s = states[it.sub_slo_id];
    return !s || (!s.result && !s.declined);
  }).length;

  return (
    <section
      className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4 space-y-3"
      aria-label="Reteach suggestions"
    >
      <header className="flex items-baseline gap-2">
        <span
          className="inline-flex items-center rounded-full bg-dars-terra px-2 py-0.5 text-[11px] font-semibold text-dars-parchment"
          aria-hidden
        >
          Reteach
        </span>
        <h2 className="font-[var(--font-cormorant)] text-xl font-bold text-dars-ink">
          {openCount > 0
            ? `Class struggled with ${openCount} sub-SLO${openCount === 1 ? "" : "s"} — reteach?`
            : "Reteach suggestions"}
        </h2>
      </header>
      <p className="text-xs text-dars-muted">
        These sub-SLOs landed below the {Math.round(threshold)}% mastery mark.
        Choose how to re-cover each one — nothing changes until you confirm.
      </p>

      <ul className="space-y-2">
        {items.map((item) => (
          <ReteachRow
            key={item.sub_slo_id}
            item={item}
            state={states[item.sub_slo_id] ?? emptyReteachItemState()}
            onSelectMode={onSelectMode}
            onConfirm={onConfirm}
            onDecline={onDecline}
          />
        ))}
      </ul>
    </section>
  );
}

function ReteachRow({
  item,
  state,
  onSelectMode,
  onConfirm,
  onDecline,
}: {
  item: ReteachSuggestionItem;
  state: ReteachItemState;
  onSelectMode: (subSloId: string, mode: ReteachMode) => void;
  onConfirm: (subSloId: string) => void;
  onDecline: (subSloId: string) => void;
}) {
  const acted = state.result !== null;
  const declined = state.declined;
  const settled = acted || declined;

  return (
    <li
      className={
        "rounded-md border border-dars-rule-light bg-dars-parchment p-3 " +
        (settled ? "opacity-75" : "")
      }
    >
      <div className="flex items-baseline gap-2 mb-1">
        <span className="font-mono text-[11px] text-dars-muted">
          {item.sub_slo_code}
        </span>
        <span className="text-[11px] font-mono text-dars-terra ml-auto">
          {Math.round(item.mastery_percent)}% mastery
        </span>
      </div>
      <p className="text-sm text-dars-ink mb-3 whitespace-pre-line">
        {item.statement}
      </p>

      {acted ? (
        <ReteachOutcome result={state.result as ReteachActionResponse} />
      ) : declined ? (
        <p className="text-xs text-dars-muted" role="status">
          Dismissed — the plan is unchanged.
        </p>
      ) : (
        <ReteachConfirm
          subSloId={item.sub_slo_id}
          state={state}
          onSelectMode={onSelectMode}
          onConfirm={onConfirm}
          onDecline={onDecline}
        />
      )}
    </li>
  );
}

function ReteachConfirm({
  subSloId,
  state,
  onSelectMode,
  onConfirm,
  onDecline,
}: {
  subSloId: string;
  state: ReteachItemState;
  onSelectMode: (subSloId: string, mode: ReteachMode) => void;
  onConfirm: (subSloId: string) => void;
  onDecline: (subSloId: string) => void;
}) {
  return (
    <div className="space-y-3">
      <fieldset className="space-y-2" disabled={state.busy}>
        <legend className="sr-only">Choose a reteach approach</legend>
        <ModeOption
          name={`reteach-mode-${subSloId}`}
          checked={state.mode === "lightweight"}
          onChange={() => onSelectMode(subSloId, "lightweight")}
          label="Re-cover in your next class"
          recommended
          hint="Flags this sub-SLO as needing rework. No new lesson, no schedule change."
        />
        <ModeOption
          name={`reteach-mode-${subSloId}`}
          checked={state.mode === "heavy"}
          onChange={() => onSelectMode(subSloId, "heavy")}
          label="Add a reteach lesson"
          hint="Uses a spare revision day if you have one; otherwise adds a new day, which can push later lessons past the end of the year."
        />
      </fieldset>

      {state.error ? (
        <p className="text-xs text-dars-terra" role="alert">
          {state.error}
        </p>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => onConfirm(subSloId)}
          disabled={state.busy}
          className="px-3 py-1.5 rounded-md bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
        >
          {state.busy ? "Applying…" : "Confirm reteach"}
        </button>
        <button
          type="button"
          onClick={() => onDecline(subSloId)}
          disabled={state.busy}
          className="px-3 py-1.5 rounded-md border border-dars-rule-light text-dars-ink-soft text-xs font-medium hover:bg-dars-parchment-deep disabled:opacity-50"
        >
          Not now
        </button>
      </div>
    </div>
  );
}

function ModeOption({
  name,
  checked,
  onChange,
  label,
  hint,
  recommended,
}: {
  name: string;
  checked: boolean;
  onChange: () => void;
  label: string;
  hint: string;
  recommended?: boolean;
}) {
  return (
    <label
      className={
        "flex gap-2 rounded-md border p-2 cursor-pointer transition-colors " +
        (checked
          ? "border-dars-terra/60 bg-dars-terra/5"
          : "border-dars-rule-light bg-white hover:bg-dars-parchment-mid")
      }
    >
      <input
        type="radio"
        name={name}
        checked={checked}
        onChange={onChange}
        className="mt-0.5 accent-dars-terra"
      />
      <span className="min-w-0">
        <span className="flex items-baseline gap-1.5">
          <span className="text-xs font-semibold text-dars-ink">{label}</span>
          {recommended ? (
            <span className="text-[10px] font-medium text-dars-muted">
              (recommended)
            </span>
          ) : null}
        </span>
        <span className="block text-[11px] text-dars-muted mt-0.5">{hint}</span>
      </span>
    </label>
  );
}

/**
 * The post-confirm message. This is the "what falls off" moment the spec calls
 * for — we translate the path + overflow consequence into something a teacher
 * reads as a calendar outcome, not raw numbers.
 */
function ReteachOutcome({ result }: { result: ReteachActionResponse }) {
  if (result.path === "lightweight") {
    return (
      <p className="text-xs text-emerald-700" role="status">
        Flagged for rework — re-cover this in your next class. Your schedule is
        unchanged.
      </p>
    );
  }

  if (result.path === "consume_flex") {
    return (
      <p className="text-xs text-emerald-700" role="status">
        Added a reteach lesson using a spare revision day — your schedule is
        unchanged.
      </p>
    );
  }

  // path === "insert" — a new day was added, which shifts the tail. Show the
  // year-end consequence plainly.
  return <InsertOutcome consequence={result.consequence} />;
}

function InsertOutcome({ consequence }: { consequence: OverflowConsequence | null }) {
  // Defensive: the contract populates `consequence` for the insert path, but if
  // it's somehow absent treat it as "added, no overflow info".
  const overflowed = consequence?.newly_overflowed_positions ?? [];

  if (overflowed.length === 0) {
    return (
      <p className="text-xs text-emerald-700" role="status">
        Added a reteach lesson on a new day — everything still fits within the
        school year.
      </p>
    );
  }

  const n = overflowed.length;
  const firstPos = consequence?.first_overflow_position ?? overflowed[0];

  return (
    <div
      className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-2"
      role="status"
    >
      <p className="text-xs font-semibold text-dars-ink">
        Added a reteach lesson — but it pushed {n} later lesson
        {n === 1 ? "" : "s"} past the end of the school year.
      </p>
      <p className="text-[11px] text-dars-muted mt-1">
        Starting at lesson #{firstPos}, {n === 1 ? "that lesson" : "those lessons"}{" "}
        no longer fit{n === 1 ? "s" : ""} on a teaching day. You&apos;ll need to
        drop a revision day, move an exam, or trim coverage to fit it back in.
      </p>
    </div>
  );
}
