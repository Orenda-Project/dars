/**
 * F4.8 — Timetable tab template.
 *
 * Top: Mon..Sat day pills indicating which days this CST meets.
 * Bottom: list of effective holidays + an add-personal-holiday flow.
 *
 * The teacher app can't fetch the raw timetable directly today (no
 * endpoint exposes it as v2). The seed sets Mon-Fri; until a timetable
 * endpoint exists we show all six day pills with all five weekday days
 * marked as meeting days. This is documented and Phase 5 will surface
 * the proper data.
 */
"use client";

import { useState } from "react";

import type { Holiday } from "@/lib/dars-api";

interface TimetableTabProps {
  effectiveDates: string[];
  holidays: Holiday[];
  busy: boolean;
  onAddOverride: (body: { date: string; name?: string; action: "add" | "remove" }) => Promise<void>;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;
// Default until a timetable endpoint lands (matches the seed: Mon-Fri).
const DEFAULT_MEETING_DAYS = new Set(["Mon", "Tue", "Wed", "Thu", "Fri"]);

export function ClassTimetableTab(props: TimetableTabProps) {
  const { effectiveDates, holidays, busy, onAddOverride } = props;
  const [date, setDate] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await onAddOverride({ date, name: name || undefined, action: "add" });
      setDate("");
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add holiday");
    }
  }

  return (
    <div className="space-y-6">
      <section>
        <h2 className="text-sm font-semibold text-dars-ink mb-2">Meeting days</h2>
        <div className="flex flex-wrap gap-2">
          {DAYS.map((d) => {
            const meets = DEFAULT_MEETING_DAYS.has(d);
            return (
              <span
                key={d}
                className={
                  "px-3 py-1 rounded-md text-xs font-medium " +
                  (meets
                    ? "bg-dars-terra/15 text-dars-terra border border-dars-terra/30"
                    : "bg-dars-parchment-deep text-dars-muted-light border border-dars-rule-light")
                }
              >
                {d}
              </span>
            );
          })}
        </div>
        <p className="text-[10px] text-dars-muted-light mt-2">
          (Defaults shown; per-CST timetable read endpoint lands in Phase 5.)
        </p>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-dars-ink mb-2">
          Effective holidays for this class
        </h2>
        {effectiveDates.length === 0 ? (
          <p className="text-xs text-dars-muted">No holidays in the resolved set.</p>
        ) : (
          <ul className="grid sm:grid-cols-2 gap-1 text-xs font-mono text-dars-ink-soft">
            {effectiveDates.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="text-sm font-semibold text-dars-ink mb-2">Sources</h2>
        <ul className="space-y-1 text-xs">
          {holidays.map((h, i) => (
            <li key={`${h.date}-${h.source}-${i}`} className="flex items-center gap-2">
              <span className="font-mono text-dars-ink-soft">{h.date}</span>
              <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-dars-parchment-deep text-dars-muted">
                {h.source}
              </span>
              {h.action ? (
                <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-dars-parchment-mid text-dars-ink-soft">
                  {h.action}
                </span>
              ) : null}
              {h.name ? <span className="text-dars-ink-soft">{h.name}</span> : null}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2 className="text-sm font-semibold text-dars-ink mb-2">
          Add a personal holiday
        </h2>
        <form onSubmit={handleAdd} className="flex flex-wrap items-end gap-2">
          <label className="flex flex-col text-xs text-dars-ink-soft">
            Date
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
              className="mt-1 px-2 py-1 border border-dars-rule-light rounded text-sm bg-white"
            />
          </label>
          <label className="flex flex-col text-xs text-dars-ink-soft flex-1 min-w-[180px]">
            Reason (optional)
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Personal day"
              className="mt-1 px-2 py-1 border border-dars-rule-light rounded text-sm bg-white"
            />
          </label>
          <button
            type="submit"
            disabled={busy || !date}
            className="px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Saving…" : "Add holiday"}
          </button>
        </form>
        {error ? (
          <p className="text-xs text-dars-terra mt-2" role="alert">{error}</p>
        ) : null}
      </section>
    </div>
  );
}
