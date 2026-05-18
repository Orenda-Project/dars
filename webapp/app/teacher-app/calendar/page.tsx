/**
 * F4.11 — /teacher-app/calendar
 *
 * Owns week navigation + fetching. Template renders.
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import { CalendarTemplate } from "@/components/templates/calendar-template";
import {
  DarsApiError,
  calendar as calendarApi,
  type CalendarResponse,
} from "@/lib/dars-api";

function isoFromOffsetWeeks(weeks: number): string {
  const now = new Date();
  const dayOfWeek = (now.getUTCDay() + 6) % 7;
  const monday = new Date(now);
  monday.setUTCDate(now.getUTCDate() - dayOfWeek + weeks * 7);
  return monday.toISOString().slice(0, 10);
}

export default function CalendarPage() {
  const [weekStart, setWeekStart] = useState<string>(() => isoFromOffsetWeeks(0));
  const [data, setData] = useState<CalendarResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (start: string) => {
    setLoading(true);
    setError(null);
    try {
      setData(await calendarApi.get(start));
    } catch (err) {
      setError(
        err instanceof DarsApiError
          ? `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`
          : err instanceof Error
          ? err.message
          : "Failed",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(weekStart);
  }, [load, weekStart]);

  const onPrev = () => {
    const next = data?.week_start
      ? addDays(data.week_start, -7)
      : isoFromOffsetWeeks(-1);
    setWeekStart(next);
  };
  const onNext = () => {
    const next = data?.week_start
      ? addDays(data.week_start, 7)
      : isoFromOffsetWeeks(1);
    setWeekStart(next);
  };
  const onToday = () => setWeekStart(isoFromOffsetWeeks(0));

  return (
    <CalendarTemplate
      data={data}
      loading={loading}
      error={error}
      onPrev={onPrev}
      onNext={onNext}
      onToday={onToday}
    />
  );
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}
