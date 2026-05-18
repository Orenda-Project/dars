/**
 * F4.11 — /teacher-app/calendar template.
 *
 * Week grid with prev/next nav. Per the plan we use Mon-Sat (D-27).
 * Slot pills deep-link into the class detail page with ?slot= so
 * clicking opens the LP slide-over directly.
 */
"use client";

import Link from "next/link";

import type { CalendarResponse } from "@/lib/dars-api";

interface CalendarTemplateProps {
  data: CalendarResponse | null;
  loading: boolean;
  error: string | null;
  onPrev: () => void;
  onNext: () => void;
  onToday: () => void;
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function CalendarTemplate(props: CalendarTemplateProps) {
  const { data, loading, error, onPrev, onNext, onToday } = props;

  if (loading && !data) return <p className="text-sm text-dars-muted">Loading calendar…</p>;
  if (error) {
    return (
      <div className="rounded-md border border-dars-terra/40 bg-dars-terra/5 p-4">
        <p className="text-sm font-semibold text-dars-ink">Couldn’t load calendar.</p>
        <p className="text-xs text-dars-muted mt-1">{error}</p>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink">
          Calendar
        </h1>
        <div className="flex items-center gap-2 text-xs">
          <button
            type="button"
            onClick={onPrev}
            className="px-2.5 py-1 rounded border border-dars-rule-light text-dars-ink hover:bg-dars-parchment-deep"
          >
            ← Prev week
          </button>
          <button
            type="button"
            onClick={onToday}
            className="px-2.5 py-1 rounded border border-dars-rule-light text-dars-ink hover:bg-dars-parchment-deep"
          >
            This week
          </button>
          <button
            type="button"
            onClick={onNext}
            className="px-2.5 py-1 rounded border border-dars-rule-light text-dars-ink hover:bg-dars-parchment-deep"
          >
            Next week →
          </button>
        </div>
      </div>

      <p className="text-xs text-dars-muted font-mono mb-3">
        {data.week_start} → {data.week_end}
      </p>

      {data.csts.length === 0 ? (
        <p className="text-sm text-dars-muted">No classes scheduled this week.</p>
      ) : null}

      <div className="space-y-6">
        {data.csts.map((cst) => (
          <CSTWeek key={cst.cst_id} cst={cst} />
        ))}
      </div>
    </div>
  );
}

function CSTWeek({ cst }: { cst: CalendarResponse["csts"][number] }) {
  // Map server days into Mon..Sat slots; missing days render as empty cells.
  const dayByISO = new Map(cst.days.map((d) => [d.day, d]));
  const cells = cst.days.length > 0 ? buildWeekArray(cst.days[0]?.day) : [];

  return (
    <section className="rounded-lg border border-dars-rule-light bg-dars-parchment-mid overflow-hidden">
      <header className="px-3 py-2 border-b border-dars-rule-light bg-dars-parchment text-sm font-semibold text-dars-ink">
        Grade {cst.grade_code} · {cst.subject_code}
      </header>
      <div className="grid grid-cols-6 divide-x divide-dars-rule-light text-xs">
        {cells.map((iso, i) => {
          const day = dayByISO.get(iso);
          return (
            <div key={iso} className="p-2 min-h-[100px] flex flex-col gap-1">
              <div className="flex items-baseline justify-between mb-1">
                <span className="font-semibold text-dars-ink-soft">
                  {DAY_LABELS[i]}
                </span>
                <span className="text-[10px] text-dars-muted-light font-mono">
                  {iso.slice(5)}
                </span>
              </div>
              {day ? (
                <>
                  {day.lesson_slots.map((slot) => (
                    <Link
                      key={slot.slot_id}
                      href={`/teacher-app/classes/${cst.cst_id}?tab=lessons&slot=${slot.slot_id}`}
                      className="block rounded px-1.5 py-1 bg-dars-terra/15 hover:bg-dars-terra/25 border border-dars-terra/30 text-[11px] text-dars-ink truncate"
                    >
                      {slot.slot_type === "revision" ? "Revision" : "Lesson"} #{slot.position}
                    </Link>
                  ))}
                  {day.assessment_slots.map((slot) => {
                    const isFA = slot.assessment_type === "formative";
                    return (
                      <Link
                        key={slot.slot_id}
                        href={`/teacher-app/classes/${cst.cst_id}?tab=assessments`}
                        className={
                          "block rounded px-1.5 py-1 border text-[11px] text-dars-ink truncate " +
                          (isFA
                            ? "bg-rose-100 hover:bg-rose-200 border-rose-300"
                            : "bg-violet-100 hover:bg-violet-200 border-violet-300")
                        }
                      >
                        {isFA ? "FA" : "SA"} #{slot.position}
                      </Link>
                    );
                  })}
                </>
              ) : null}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/**
 * Build a 6-day array of ISO dates starting from the Monday of the
 * week the given day belongs to (or sensible default if undefined).
 */
function buildWeekArray(anchor: string | undefined): string[] {
  if (!anchor) return [];
  const d = new Date(anchor + "T00:00:00Z");
  const dayOfWeek = (d.getUTCDay() + 6) % 7; // 0 = Mon … 6 = Sun
  const monday = new Date(d);
  monday.setUTCDate(d.getUTCDate() - dayOfWeek);
  return Array.from({ length: 6 }, (_, i) => {
    const x = new Date(monday);
    x.setUTCDate(monday.getUTCDate() + i);
    return x.toISOString().slice(0, 10);
  });
}
