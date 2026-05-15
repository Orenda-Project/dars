"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  getCalendar,
  type CalendarDayResponse,
  type CalendarPeriod,
} from "@/lib/school-api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function isoToDate(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function toIso(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function getMondayOfWeek(d: Date): Date {
  const day = d.getDay(); // 0=Sun
  const diff = day === 0 ? -6 : 1 - day;
  const mon = new Date(d);
  mon.setDate(d.getDate() + diff);
  return mon;
}

function formatWeekHeader(weekStart: string): string {
  const start = isoToDate(weekStart);
  const end = new Date(start);
  end.setDate(start.getDate() + 5);
  const startStr = start.toLocaleDateString("en-PK", { day: "numeric", month: "short" });
  const endStr = end.toLocaleDateString("en-PK", { day: "numeric", month: "short", year: "numeric" });
  return `${startStr} – ${endStr}`;
}

function isToday(iso: string): boolean {
  return iso === toIso(new Date());
}

// ---------------------------------------------------------------------------
// Period pill
// ---------------------------------------------------------------------------

const LP_TYPE_COLORS: Record<string, string> = {
  Reading: "bg-blue-100 text-blue-800 border-blue-200",
  Grammar: "bg-indigo-100 text-indigo-800 border-indigo-200",
  Concept: "bg-orange-100 text-orange-800 border-orange-200",
  Practice: "bg-yellow-100 text-yellow-800 border-yellow-200",
  Revision: "bg-amber-100 text-amber-800 border-amber-200",
  Introduction: "bg-blue-100 text-blue-800 border-blue-200",
};

function buildClassHref(period: CalendarPeriod): string {
  if (period.period_type === "assessment" && period.assessment_slot_id) {
    return `/teacher-app/classes/${period.cst_id}?tab=assessments&assessmentSlot=${period.assessment_slot_id}`;
  }
  if (period.period_type === "lesson" && period.slot_id) {
    return `/teacher-app/classes/${period.cst_id}?tab=lessons&slot=${period.slot_id}`;
  }
  return `/teacher-app/classes/${period.cst_id}`;
}

function PeriodPill({ period }: { period: CalendarPeriod }) {
  const href = buildClassHref(period);

  if (period.period_type === "assessment") {
    const isFa = period.assessment_type === "formative";
    const colorCls = isFa
      ? "bg-rose-100 text-rose-800 border-rose-200"
      : "bg-violet-100 text-violet-800 border-violet-200";
    return (
      <Link
        href={href}
        className={`block px-2 py-1.5 rounded border text-[10px] font-medium leading-tight no-underline hover:opacity-80 transition-opacity ${colorCls}`}
      >
        <div className="flex items-center gap-1 mb-0.5">
          <span className="font-bold uppercase text-[9px] px-1 py-0.5 rounded bg-white/50">
            {isFa ? "FA" : "SA"}
          </span>
          <span className="truncate font-semibold">{period.class_name}</span>
        </div>
        <div className="truncate text-[9px] opacity-80">{period.subject}</div>
        {period.assessment_title && (
          <div className="truncate text-[9px] opacity-70 mt-0.5">{period.assessment_title}</div>
        )}
        {period.assessment_status === "completed" && (
          <div className="text-[9px] font-semibold text-green-700 mt-0.5">✓ done</div>
        )}
      </Link>
    );
  }

  if (period.period_type === "lesson") {
    const colorCls =
      LP_TYPE_COLORS[period.lp_type ?? ""] ?? "bg-amber-100 text-amber-800 border-amber-200";
    return (
      <Link
        href={href}
        className={`block px-2 py-1.5 rounded border text-[10px] font-medium leading-tight no-underline hover:opacity-80 transition-opacity ${colorCls}`}
      >
        <div className="truncate font-semibold">{period.class_name}</div>
        <div className="truncate text-[9px] opacity-75">{period.subject}</div>
        {period.title && (
          <div className="truncate text-[9px] opacity-70 mt-0.5">{period.title}</div>
        )}
        {period.lesson_status === "taught" && (
          <div className="text-[9px] font-semibold text-green-700 mt-0.5">✓ taught</div>
        )}
      </Link>
    );
  }

  // no_breakdown — class is on timetable but no lesson planned yet
  return (
    <Link
      href={href}
      className="block px-2 py-1.5 rounded border border-dashed border-gray-300 text-[10px] font-medium leading-tight no-underline hover:opacity-80 transition-opacity text-gray-500"
    >
      <div className="truncate font-semibold">{period.class_name}</div>
      <div className="truncate text-[9px] opacity-75">{period.subject}</div>
      <div className="text-[9px] opacity-60 mt-0.5 italic">No plan yet</div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// Day column
// ---------------------------------------------------------------------------

function DayColumn({ day, dayIndex }: { day: CalendarDayResponse; dayIndex: number }) {
  const today = isToday(day.date);
  const dayNum = isoToDate(day.date).getDate();
  const empty = day.periods.length === 0;

  return (
    <div className={`flex flex-col min-h-[200px] ${today ? "bg-amber-50 rounded-lg" : ""}`}>
      {/* Day header */}
      <div className={`px-2 py-2 text-center border-b ${today ? "border-amber-200" : "border-gray-100"}`}>
        <p className={`text-[10px] font-semibold uppercase tracking-wide ${today ? "text-amber-700" : "text-gray-400"}`}>
          {DAY_LABELS[dayIndex]}
        </p>
        <p className={`text-sm font-bold mt-0.5 ${today ? "text-amber-700" : "text-gray-700"}`}>
          {dayNum}
        </p>
      </div>

      {/* Periods */}
      <div className="flex-1 px-1.5 py-2 space-y-1.5">
        {empty ? (
          <div className="h-full flex items-center justify-center">
            <div className="w-full h-full border border-dashed border-gray-200 rounded-md" />
          </div>
        ) : (
          day.periods.map((period, idx) => (
            <PeriodPill key={`${period.cst_id}-${idx}`} period={period} />
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function CalendarSkeleton() {
  return (
    <div className="grid grid-cols-6 gap-px bg-gray-100 rounded-xl overflow-hidden border border-gray-200">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="bg-white min-h-[200px]">
          <div className="px-2 py-2 border-b border-gray-100 text-center">
            <div className="h-2.5 bg-gray-100 rounded animate-pulse w-8 mx-auto mb-1" />
            <div className="h-4 bg-gray-100 rounded animate-pulse w-5 mx-auto" />
          </div>
          <div className="px-1.5 py-2 space-y-1.5">
            {i % 2 === 0 && <div className="h-8 bg-gray-50 rounded animate-pulse" />}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState<string>(() => {
    const mon = getMondayOfWeek(new Date());
    return toIso(mon);
  });
  const [days, setDays] = useState<CalendarDayResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getCalendar(weekStart)
      .then((data) => setDays(data.items.slice(0, 6))) // Mon–Sat only
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, [weekStart]);

  function prevWeek() {
    const d = isoToDate(weekStart);
    d.setDate(d.getDate() - 7);
    setWeekStart(toIso(d));
  }

  function nextWeek() {
    const d = isoToDate(weekStart);
    d.setDate(d.getDate() + 7);
    setWeekStart(toIso(d));
  }

  function goToday() {
    setWeekStart(toIso(getMondayOfWeek(new Date())));
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-5 flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Calendar</h1>
          <p className="text-sm text-gray-500 mt-1">{formatWeekHeader(weekStart)}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={goToday}
            className="px-3 py-1.5 text-xs font-semibold rounded-md border border-gray-300 text-gray-600 hover:border-gray-500 hover:text-gray-900 transition-colors bg-white cursor-pointer"
          >
            Today
          </button>
          <button
            type="button"
            onClick={prevWeek}
            className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:text-amber-600 hover:border-amber-300 transition-colors bg-white cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
          <button
            type="button"
            onClick={nextWeek}
            className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:text-amber-600 hover:border-amber-300 transition-colors bg-white cursor-pointer"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700 mb-4">
          {error}
        </div>
      )}

      {loading ? (
        <CalendarSkeleton />
      ) : (
        <div className="overflow-x-auto">
          <div className="min-w-[560px]">
            <div className="grid grid-cols-6 gap-px bg-gray-200 rounded-xl overflow-hidden border border-gray-200">
              {days.map((day, i) => (
                <div key={day.date} className="bg-white">
                  <DayColumn day={day} dayIndex={i} />
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Legend */}
      {!loading && !error && (
        <div className="mt-4 flex flex-wrap gap-3 text-[10px] text-gray-500">
          <div className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-amber-100 border border-amber-200" />
            Lesson
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-rose-100 border border-rose-200" />
            Formative assessment
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded bg-violet-100 border border-violet-200" />
            Summative assessment
          </div>
          <div className="flex items-center gap-1">
            <span className="inline-block w-3 h-3 rounded border border-dashed border-gray-300" />
            No plan yet
          </div>
        </div>
      )}
    </div>
  );
}
