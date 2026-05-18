/**
 * F5.17 — Holiday management at org + school scope.
 *
 * Org tab: per-AY org holidays (add only — server has no delete).
 * School tab: school overrides (add/remove against the org defaults).
 * Teacher-level overrides are in the teacher app (F4.8).
 */
"use client";

import { useCallback, useEffect, useState } from "react";

import {
  admin,
  adminHolidays,
  DarsApiError,
  holidays as holidaysApi,
  tenancy as tenancyApi,
  type AcademicYear,
  type AdminMeResponse,
  type Holiday,
  type School,
} from "@/lib/dars-api";

type Tab = "org" | "school";

export default function HolidaysPage() {
  const [tab, setTab] = useState<Tab>("org");
  const [me, setMe] = useState<AdminMeResponse | null>(null);
  const [schools, setSchools] = useState<School[]>([]);
  const [academicYears, setAcademicYears] = useState<AcademicYear[]>([]);
  const [selectedAyId, setSelectedAyId] = useState<string>("");
  const [selectedSchoolId, setSelectedSchoolId] = useState<string>("");
  const [orgHolidays, setOrgHolidays] = useState<Holiday[]>([]);
  const [schoolHolidays, setSchoolHolidays] = useState<Holiday[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [newDate, setNewDate] = useState("");
  const [newName, setNewName] = useState("");
  const [newAction, setNewAction] = useState<"add" | "remove">("add");

  const loadFilters = useCallback(async () => {
    try {
      const [m, { items: ss }] = await Promise.all([
        admin.me(),
        tenancyApi.getSchools(),
      ]);
      setMe(m);
      setSchools(ss);
      if (ss[0]) {
        setSelectedSchoolId(ss[0].id);
        const { items: ays } = await tenancyApi.getAcademicYears(ss[0].id);
        setAcademicYears(ays);
        if (ays[0]) setSelectedAyId(ays[0].id);
      }
    } catch (err) {
      setError(formatErr(err));
    }
  }, []);

  useEffect(() => {
    loadFilters();
  }, [loadFilters]);

  const loadOrgHolidays = useCallback(async () => {
    if (!me) return;
    try {
      const res = await holidaysApi.getOrgHolidays(me.org_id);
      setOrgHolidays(res.items);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [me]);

  const loadSchoolHolidays = useCallback(async () => {
    if (!selectedSchoolId) return;
    try {
      const res = await holidaysApi.getSchoolHolidays(selectedSchoolId);
      setSchoolHolidays(res.items);
    } catch (err) {
      setError(formatErr(err));
    }
  }, [selectedSchoolId]);

  useEffect(() => {
    if (tab === "org") loadOrgHolidays();
    else loadSchoolHolidays();
  }, [tab, loadOrgHolidays, loadSchoolHolidays]);

  async function handleSwitchSchool(id: string) {
    setSelectedSchoolId(id);
    try {
      const { items } = await tenancyApi.getAcademicYears(id);
      setAcademicYears(items);
      setSelectedAyId(items[0]?.id ?? "");
    } catch (err) {
      setError(formatErr(err));
    }
  }

  async function handleAddOrg(e: React.FormEvent) {
    e.preventDefault();
    if (!me || !selectedAyId) return;
    setBusy(true);
    setError(null);
    try {
      await adminHolidays.addOrgHoliday(me.org_id, {
        academic_year_id: selectedAyId,
        date: newDate,
        name: newName,
      });
      setNewDate("");
      setNewName("");
      await loadOrgHolidays();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAddSchool(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedSchoolId) return;
    setBusy(true);
    setError(null);
    try {
      await adminHolidays.addSchoolOverride(selectedSchoolId, {
        date: newDate,
        name: newName || undefined,
        action: newAction,
      });
      setNewDate("");
      setNewName("");
      await loadSchoolHolidays();
    } catch (err) {
      setError(formatErr(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="max-w-2xl">
      <h1 className="font-[var(--font-cormorant)] text-3xl font-bold text-dars-ink mb-4">
        Holidays
      </h1>

      <nav className="border-b border-dars-rule-light mb-4 flex gap-1">
        {(["org", "school"] as const).map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={
              "px-3 py-2 text-sm border-b-2 -mb-px " +
              (tab === t
                ? "border-dars-terra text-dars-terra font-semibold"
                : "border-transparent text-dars-muted hover:text-dars-ink")
            }
          >
            {t === "org" ? "Org-level" : "School overrides"}
          </button>
        ))}
      </nav>

      {error ? <p className="text-sm text-dars-terra mb-3">{error}</p> : null}

      {tab === "org" ? (
        <>
          <div className="mb-3">
            <label className="text-xs text-dars-ink-soft">
              Academic year:{" "}
              <select
                value={selectedAyId}
                onChange={(e) => setSelectedAyId(e.target.value)}
                className="ml-1 px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
              >
                {academicYears.map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </label>
          </div>

          <form onSubmit={handleAddOrg} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 grid grid-cols-3 gap-2 items-end">
            <label>
              <span className="text-xs text-dars-ink-soft">Date</span>
              <input required type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} className="input" />
            </label>
            <label className="col-span-2">
              <span className="text-xs text-dars-ink-soft">Name</span>
              <input required value={newName} onChange={(e) => setNewName(e.target.value)} className="input" placeholder="e.g. Eid" />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="col-span-3 px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold disabled:opacity-50"
            >
              {busy ? "Saving…" : "Add org holiday"}
            </button>
            <style jsx>{`
              .input {
                margin-top: 0.25rem; width: 100%;
                padding: 0.4rem 0.5rem;
                border-radius: 0.375rem;
                border: 1px solid var(--color-dars-rule-light);
                background: white;
                font-size: 0.875rem;
              }
            `}</style>
          </form>

          <HolidayList items={orgHolidays} />
        </>
      ) : (
        <>
          <div className="mb-3">
            <label className="text-xs text-dars-ink-soft">
              School:{" "}
              <select
                value={selectedSchoolId}
                onChange={(e) => handleSwitchSchool(e.target.value)}
                className="ml-1 px-2 py-1 rounded border border-dars-rule-light bg-white text-sm"
              >
                {schools.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            </label>
          </div>

          <form onSubmit={handleAddSchool} className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-3 mb-4 grid grid-cols-4 gap-2 items-end">
            <label>
              <span className="text-xs text-dars-ink-soft">Date</span>
              <input required type="date" value={newDate} onChange={(e) => setNewDate(e.target.value)} className="input" />
            </label>
            <label>
              <span className="text-xs text-dars-ink-soft">Action</span>
              <select value={newAction} onChange={(e) => setNewAction(e.target.value as "add" | "remove")} className="input">
                <option value="add">add</option>
                <option value="remove">remove</option>
              </select>
            </label>
            <label className="col-span-2">
              <span className="text-xs text-dars-ink-soft">Name (optional)</span>
              <input value={newName} onChange={(e) => setNewName(e.target.value)} className="input" />
            </label>
            <button
              type="submit"
              disabled={busy}
              className="col-span-4 px-3 py-1.5 rounded bg-dars-terra text-dars-parchment text-xs font-semibold disabled:opacity-50"
            >
              {busy ? "Saving…" : "Add override"}
            </button>
            <style jsx>{`
              .input {
                margin-top: 0.25rem; width: 100%;
                padding: 0.4rem 0.5rem;
                border-radius: 0.375rem;
                border: 1px solid var(--color-dars-rule-light);
                background: white;
                font-size: 0.875rem;
              }
            `}</style>
          </form>

          <HolidayList items={schoolHolidays} />
        </>
      )}
    </div>
  );
}

function HolidayList({ items }: { items: Holiday[] }) {
  if (items.length === 0) return <p className="text-xs text-dars-muted">No entries.</p>;
  return (
    <ul className="text-xs space-y-1">
      {items.map((h, i) => (
        <li key={`${h.date}-${h.source}-${i}`} className="flex items-center gap-2 px-2 py-1.5 rounded bg-dars-parchment-mid border border-dars-rule-light">
          <span className="font-mono text-dars-ink-soft">{h.date}</span>
          <span className="text-[10px] uppercase tracking-wide px-1.5 rounded bg-dars-parchment text-dars-muted">{h.source}</span>
          {h.action ? <span className="text-[10px] uppercase tracking-wide px-1.5 rounded bg-dars-parchment text-dars-ink-soft">{h.action}</span> : null}
          {h.name ? <span className="text-dars-ink-soft">{h.name}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed";
}
