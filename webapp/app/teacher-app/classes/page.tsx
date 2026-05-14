"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  getMyClasses,
  getAcademicYears,
  getGrades,
  getSubjects,
  createTeacherClass,
  type MyClassEntry,
  type AcademicYearRead,
  type TeacherClassCreated,
  type GradeOption,
  type SubjectOption,
} from "@/lib/school-api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DAYS = [
  { label: "Mon", value: 0 },
  { label: "Tue", value: 1 },
  { label: "Wed", value: 2 },
  { label: "Thu", value: 3 },
  { label: "Fri", value: 4 },
  { label: "Sat", value: 5 },
];

// ---------------------------------------------------------------------------
// ProgressBar
// ---------------------------------------------------------------------------

function ProgressBar({ taught, total }: { taught: number; total: number }) {
  const pct = total > 0 ? Math.round((taught / total) * 100) : 0;
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span>{taught} taught</span>
        <span>{total} total</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div
          className="bg-amber-500 h-1.5 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DayPills
// ---------------------------------------------------------------------------

function DayPills({ days }: { days: number[] | undefined }) {
  if (!days || days.length === 0) return (
    <span className="text-[10px] text-gray-400 italic">No schedule set</span>
  );
  return (
    <div className="flex gap-1 flex-wrap">
      {DAYS.map((d) =>
        days.includes(d.value) ? (
          <span
            key={d.value}
            className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 border border-amber-200"
          >
            {d.label}
          </span>
        ) : null
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ClassCard (grid view)
// ---------------------------------------------------------------------------

function ClassCard({ entry, pending }: { entry: MyClassEntry; pending?: boolean }) {
  const totalSlots = entry.taught_count + (entry.next_slot ? 1 : 0);

  return (
    <Link
      href={`/teacher-app/classes/${entry.cst_id}`}
      className="block bg-white border border-gray-200 rounded-xl shadow-sm p-5 hover:border-amber-300 hover:shadow-md transition-all no-underline group"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-semibold text-gray-400 uppercase tracking-wide">
              Grade {entry.grade}
            </span>
            {pending && (
              <span className="text-[10px] font-semibold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">
                Breakdown generating...
              </span>
            )}
          </div>
          <h3 className="font-semibold text-gray-900 text-sm group-hover:text-amber-700 transition-colors">
            {entry.class_name}
          </h3>
          <p className="text-xs text-gray-500 mt-0.5">{entry.subject}</p>
          {entry.book_title && (
            <p className="text-xs text-gray-400 mt-0.5 italic truncate">{entry.book_title}</p>
          )}
        </div>
        <div className="shrink-0">
          <span className="text-xs bg-gray-100 text-gray-600 px-2.5 py-1 rounded-full font-medium">
            {entry.chapter_count} ch
          </span>
        </div>
      </div>

      <div className="mt-2">
        <DayPills days={entry.timetable_days} />
      </div>

      <ProgressBar taught={entry.taught_count} total={totalSlots > 0 ? totalSlots : entry.chapter_count} />

      {entry.next_slot && (
        <div className="mt-3 pt-3 border-t border-gray-100">
          <p className="text-[10px] uppercase tracking-widest text-gray-400 mb-1">Next lesson</p>
          <p className="text-xs text-gray-700 truncate font-medium">{entry.next_slot.title}</p>
          <p className="text-xs text-gray-400">{entry.next_slot.lp_type} · Day {entry.next_slot.day_number}</p>
        </div>
      )}

      <div className="mt-3 flex items-center gap-1 text-xs text-amber-600 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
        View details
        <svg xmlns="http://www.w3.org/2000/svg" className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="5" y1="12" x2="19" y2="12" />
          <polyline points="12 5 19 12 12 19" />
        </svg>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// ClassRow (group view — compact list row)
// ---------------------------------------------------------------------------

function ClassRow({ entry, pending }: { entry: MyClassEntry; pending?: boolean }) {
  const totalSlots = entry.taught_count + (entry.next_slot ? 1 : 0);
  const total = totalSlots > 0 ? totalSlots : entry.chapter_count;
  const pct = total > 0 ? Math.round((entry.taught_count / total) * 100) : 0;

  return (
    <Link
      href={`/teacher-app/classes/${entry.cst_id}`}
      className="flex items-center gap-4 px-4 py-3 bg-white hover:bg-amber-50 transition-colors no-underline group border-b border-gray-100 last:border-0"
    >
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-900 group-hover:text-amber-700 transition-colors">
            {entry.class_name}
          </span>
          <span className="text-xs text-gray-500">{entry.subject}</span>
          {pending && (
            <span className="text-[10px] font-semibold bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full border border-amber-200">
              Generating...
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 mt-1">
          <DayPills days={entry.timetable_days} />
          {entry.book_title && (
            <span className="text-[10px] text-gray-400 italic truncate max-w-[120px]">{entry.book_title}</span>
          )}
        </div>
      </div>
      <div className="shrink-0 flex items-center gap-3">
        <div className="text-right">
          <p className="text-xs text-gray-500">{pct}%</p>
          <div className="w-16 bg-gray-100 rounded-full h-1 mt-0.5">
            <div className="bg-amber-500 h-1 rounded-full" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <span className="text-xs text-gray-400">{entry.chapter_count} ch</span>
      </div>
    </Link>
  );
}

// ---------------------------------------------------------------------------
// CreateClassModal
// ---------------------------------------------------------------------------

interface CreateClassModalProps {
  onClose: () => void;
  onCreated: (result: TeacherClassCreated) => void;
}

function CreateClassModal({ onClose, onCreated }: CreateClassModalProps) {
  const [years, setYears] = useState<AcademicYearRead[]>([]);
  const [subjects, setSubjects] = useState<SubjectOption[]>([]);
  const [grades, setGrades] = useState<GradeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [academicYearId, setAcademicYearId] = useState("");
  const [gradeId, setGradeId] = useState<number>(0);
  const [section, setSection] = useState("A");
  const [subjectId, setSubjectId] = useState<number>(0);

  useEffect(() => {
    Promise.all([
      getAcademicYears().then((r) => r.items),
      getSubjects(),
      getGrades(),
    ])
      .then(([yrs, subs, grs]) => {
        setYears(yrs);
        setSubjects(subs);
        setGrades(grs);
        if (yrs.length > 0) setAcademicYearId(yrs[0].id);
        if (subs.length > 0) setSubjectId(subs[0].id);
        if (grs.length > 0) setGradeId(grs[0].id);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load options"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!academicYearId || !subjectId || !gradeId) {
      setError("Please fill in all fields.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const result = await createTeacherClass({
        grade_id: gradeId,
        section,
        subject_id: subjectId,
        academic_year_id: academicYearId,
      });
      onCreated(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create class");
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 overflow-hidden">
        <div className="bg-gray-900 px-6 py-4">
          <h2 className="text-base font-semibold text-white">Create Class</h2>
          <p className="text-xs text-gray-400 mt-0.5">Select grade, section, and subject to get started.</p>
        </div>

        <div className="px-6 py-5 space-y-4">
          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{error}</p>
          )}

          {loading ? (
            <p className="text-sm text-gray-400 animate-pulse">Loading options...</p>
          ) : (
            <>
              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Academic Year</label>
                {years.length === 0 ? (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">
                    No academic years found. Ask your school admin to set up the academic year first.
                  </p>
                ) : (
                  <select
                    value={academicYearId}
                    onChange={(e) => setAcademicYearId(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
                  >
                    {years.map((y) => (
                      <option key={y.id} value={y.id}>{y.name}</option>
                    ))}
                  </select>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-500 mb-1">Grade</label>
                  {grades.length === 0 ? (
                    <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">No grades available.</p>
                  ) : (
                    <select
                      value={gradeId}
                      onChange={(e) => setGradeId(Number(e.target.value))}
                      className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
                    >
                      {grades.map((g) => (
                        <option key={g.id} value={g.id}>{g.display_name}</option>
                      ))}
                    </select>
                  )}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-500 mb-1">Section</label>
                  <input
                    type="text"
                    placeholder="A"
                    value={section}
                    onChange={(e) => setSection(e.target.value)}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-gray-500 mb-1">Subject</label>
                {subjects.length === 0 ? (
                  <p className="text-xs text-amber-600 bg-amber-50 border border-amber-200 rounded px-3 py-2">No subjects available.</p>
                ) : (
                  <select
                    value={subjectId}
                    onChange={(e) => setSubjectId(Number(e.target.value))}
                    className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm text-gray-900 bg-white focus:outline-none focus:ring-1 focus:ring-amber-500"
                  >
                    {subjects.map((s) => (
                      <option key={s.id} value={s.id}>{s.display_name}</option>
                    ))}
                  </select>
                )}
              </div>
            </>
          )}
        </div>

        <div className="px-6 py-4 border-t border-gray-100 flex items-center justify-between bg-gray-50">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-4 py-2 text-sm font-semibold rounded-md border border-gray-300 text-gray-600 hover:border-gray-500 hover:text-gray-900 transition-colors cursor-pointer bg-white disabled:opacity-40"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={(e) => void handleSubmit(e as unknown as React.FormEvent)}
            disabled={saving || loading || years.length === 0 || grades.length === 0 || subjects.length === 0}
            className="px-5 py-2 bg-amber-600 text-white text-sm font-semibold rounded-md hover:bg-amber-700 transition-colors cursor-pointer border-none disabled:opacity-60 flex items-center gap-2"
          >
            {saving && (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function GridIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
    </svg>
  );
}

function GroupIcon() {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function MyClassesPage() {
  const [classes, setClasses] = useState<MyClassEntry[]>([]);
  const [pendingCstIds, setPendingCstIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const [viewMode, setViewMode] = useState<"grid" | "group">(() => {
    if (typeof window !== "undefined") {
      return (localStorage.getItem("classes_view_mode") as "grid" | "group") ?? "grid";
    }
    return "grid";
  });

  const [gradeFilter, setGradeFilter] = useState<number | null>(null);
  const [subjectFilter, setSubjectFilter] = useState<string | null>(null);

  useEffect(() => {
    getMyClasses()
      .then((data) => setClasses(data.items))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load"))
      .finally(() => setLoading(false));
  }, []);

  function toggleViewMode() {
    setViewMode((prev) => {
      const next = prev === "grid" ? "group" : "grid";
      localStorage.setItem("classes_view_mode", next);
      return next;
    });
  }

  function handleCreated(result: TeacherClassCreated) {
    setShowModal(false);
    setPendingCstIds((prev) => new Set([...prev, result.cst_id]));
    setTimeout(() => {
      getMyClasses()
        .then((data) => setClasses(data.items))
        .catch(() => {});
    }, 800);
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-gray-400 animate-pulse">Loading your classes...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
        {error}
      </div>
    );
  }

  // Unique grades and subjects for filter chips
  const allGrades = [...new Set(classes.map((c) => c.grade))].sort((a, b) => a - b);
  const allSubjects = [...new Set(classes.map((c) => c.subject))].sort();

  const filtered = classes.filter((c) => {
    if (gradeFilter !== null && c.grade !== gradeFilter) return false;
    if (subjectFilter !== null && c.subject !== subjectFilter) return false;
    return true;
  });

  // Group by grade for group view
  const byGrade = allGrades.reduce<Record<number, MyClassEntry[]>>((acc, g) => {
    acc[g] = filtered.filter((c) => c.grade === g);
    return acc;
  }, {});

  return (
    <div>
      {showModal && (
        <CreateClassModal
          onClose={() => setShowModal(false)}
          onCreated={handleCreated}
        />
      )}

      {/* Header */}
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">My Classes</h1>
          <p className="text-sm text-gray-500 mt-1">
            {classes.length === 0
              ? "No classes yet."
              : `${classes.length} class${classes.length !== 1 ? "es" : ""}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {classes.length > 0 && (
            <button
              type="button"
              onClick={toggleViewMode}
              title={viewMode === "grid" ? "Switch to group view" : "Switch to grid view"}
              className="p-2 rounded-lg border border-gray-200 text-gray-500 hover:text-amber-600 hover:border-amber-300 transition-colors bg-white cursor-pointer"
            >
              {viewMode === "grid" ? <GroupIcon /> : <GridIcon />}
            </button>
          )}
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-sm font-semibold rounded-lg hover:bg-amber-700 transition-colors cursor-pointer border-none"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Create Class
          </button>
        </div>
      </div>

      {classes.length === 0 ? (
        <div className="text-center py-16">
          <div className="text-4xl mb-3">🏫</div>
          <p className="text-gray-500 font-medium">No classes yet.</p>
          <p className="text-sm text-gray-400 mt-1">Create your first class to get started.</p>
          <button
            type="button"
            onClick={() => setShowModal(true)}
            className="mt-4 inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 text-white text-sm font-semibold rounded-lg hover:bg-amber-700 transition-colors cursor-pointer border-none"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Create Class
          </button>
        </div>
      ) : (
        <>
          {/* Filter chips */}
          {(allGrades.length > 1 || allSubjects.length > 1) && (
            <div className="flex flex-wrap gap-2 mb-4">
              <button
                type="button"
                onClick={() => { setGradeFilter(null); setSubjectFilter(null); }}
                className={`text-xs px-3 py-1 rounded-full border font-medium transition-colors cursor-pointer ${
                  gradeFilter === null && subjectFilter === null
                    ? "bg-gray-900 text-white border-gray-900"
                    : "bg-white text-gray-600 border-gray-200 hover:border-gray-400"
                }`}
              >
                All
              </button>
              {allGrades.map((g) => (
                <button
                  key={`g-${g}`}
                  type="button"
                  onClick={() => setGradeFilter(gradeFilter === g ? null : g)}
                  className={`text-xs px-3 py-1 rounded-full border font-medium transition-colors cursor-pointer ${
                    gradeFilter === g
                      ? "bg-amber-600 text-white border-amber-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-amber-300"
                  }`}
                >
                  Grade {g}
                </button>
              ))}
              {allSubjects.map((s) => (
                <button
                  key={`s-${s}`}
                  type="button"
                  onClick={() => setSubjectFilter(subjectFilter === s ? null : s)}
                  className={`text-xs px-3 py-1 rounded-full border font-medium transition-colors cursor-pointer ${
                    subjectFilter === s
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-200 hover:border-blue-300"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {filtered.length === 0 ? (
            <p className="text-sm text-gray-400 py-8 text-center">No classes match the selected filters.</p>
          ) : viewMode === "grid" ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filtered.map((c) => (
                <ClassCard key={c.cst_id} entry={c} pending={pendingCstIds.has(c.cst_id)} />
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {allGrades
                .filter((g) => (gradeFilter === null || g === gradeFilter) && byGrade[g]?.length > 0)
                .map((grade) => {
                  const gradeClasses = byGrade[grade].filter(
                    (c) => subjectFilter === null || c.subject === subjectFilter
                  );
                  if (gradeClasses.length === 0) return null;
                  return (
                    <div key={grade} className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
                      <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
                        <span className="text-xs font-bold text-gray-700 uppercase tracking-wide">
                          Grade {grade}
                        </span>
                        <span className="text-xs text-gray-400">{gradeClasses.length} class{gradeClasses.length !== 1 ? "es" : ""}</span>
                      </div>
                      <div>
                        {gradeClasses.map((c) => (
                          <ClassRow key={c.cst_id} entry={c} pending={pendingCstIds.has(c.cst_id)} />
                        ))}
                      </div>
                    </div>
                  );
                })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
