"use client";

import { useState, useEffect, useCallback } from "react";
import {
  getAcademicYears,
  createAcademicYear,
  addHoliday,
  getClasses,
  createClass,
  assignSubject,
  setTimetable,
  getChapterPlans,
  generateLessonSlots,
  getLessonSlots,
  markTaught,
  autoScheduleFAs,
  getAssessmentSlots,
  updateAssessmentSlot,
  getToday,
  getClass,
  type AcademicYearRead,
  type SchoolClassRead,
  type CSTRead,
  type ChapterPlanWithDates,
  type ClassLessonSlotRead,
  type AssessmentSlotRead,
  type TodaySlotEntry,
  type SchoolClassWithSubjects,
} from "@/lib/school-api";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("en-PK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDateShort(iso: string | null | undefined) {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("en-PK", {
    day: "numeric",
    month: "short",
  });
}

const CHAPTER_COLORS = [
  "bg-blue-100 text-blue-800 border-blue-200",
  "bg-emerald-100 text-emerald-800 border-emerald-200",
  "bg-violet-100 text-violet-800 border-violet-200",
  "bg-amber-100 text-amber-800 border-amber-200",
  "bg-rose-100 text-rose-800 border-rose-200",
  "bg-cyan-100 text-cyan-800 border-cyan-200",
  "bg-orange-100 text-orange-800 border-orange-200",
  "bg-pink-100 text-pink-800 border-pink-200",
  "bg-teal-100 text-teal-800 border-teal-200",
  "bg-indigo-100 text-indigo-800 border-indigo-200",
  "bg-lime-100 text-lime-800 border-lime-200",
  "bg-red-100 text-red-800 border-red-200",
];

const LP_TYPE_BADGE: Record<string, string> = {
  "Reading": "bg-blue-100 text-blue-800",
  "Comprehension — Word Meanings": "bg-emerald-100 text-emerald-800",
  "Comprehension — Q&A": "bg-teal-100 text-teal-800",
  "Grammar": "bg-violet-100 text-violet-800",
  "Creative Writing": "bg-orange-100 text-orange-800",
  "Revision": "bg-red-100 text-red-800",
  "Concrete": "bg-cyan-100 text-cyan-800",
  "Pictorial & Abstract": "bg-indigo-100 text-indigo-800",
  "Word Problems": "bg-amber-100 text-amber-800",
};

const SAMPLE_LP_HTML = `
<div style="font-family: Georgia, serif; line-height: 1.7; color: #1c1410;">
  <h2 style="font-size: 1.1rem; font-weight: bold; margin-bottom: 0.25rem;">Reading: The Clever Fox</h2>
  <p style="font-size: 0.75rem; color: #7a6b62; margin-bottom: 1.25rem;">English · Grade 5 · Chapter 1 · LP Type: Reading</p>
  <h3 style="font-size: 0.85rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; color: #7a6b62; margin-bottom: 0.5rem;">Learning Objectives</h3>
  <ul style="margin: 0 0 1rem 1.2rem; font-size: 0.875rem;">
    <li>Students will read the passage aloud with correct pronunciation and pacing.</li>
    <li>Students will identify new vocabulary words and infer their meaning from context.</li>
    <li>Students will answer literal comprehension questions about the story.</li>
  </ul>
  <h3 style="font-size: 0.85rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; color: #7a6b62; margin-bottom: 0.5rem;">Warm-Up (5 min)</h3>
  <p style="font-size: 0.875rem; margin-bottom: 1rem;">Ask students: <em>"Have you ever seen a fox? What do you know about foxes?"</em> Elicit 3–4 responses. Connect to the idea of animals being clever.</p>
  <h3 style="font-size: 0.85rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; color: #7a6b62; margin-bottom: 0.5rem;">Main Activity (25 min)</h3>
  <p style="font-size: 0.875rem; margin-bottom: 0.5rem;"><strong>Step 1 — Teacher reads aloud (8 min):</strong> Read the first two paragraphs while students follow along. Pause to model stress and intonation.</p>
  <p style="font-size: 0.875rem; margin-bottom: 0.5rem;"><strong>Step 2 — Paired reading (10 min):</strong> Students read in pairs, alternating paragraphs. Circulate and prompt correct pronunciation.</p>
  <p style="font-size: 0.875rem; margin-bottom: 0.5rem;"><strong>Step 3 — Vocabulary (7 min):</strong> Write <em>cunning, sly, outwit</em> on the board. Students guess meanings from the story, then confirm with the glossary.</p>
  <h3 style="font-size: 0.85rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; color: #7a6b62; margin-bottom: 0.5rem;">Wrap-Up (5 min)</h3>
  <p style="font-size: 0.875rem; margin-bottom: 1rem;">Ask: <em>"Was the fox kind or unkind? Why?"</em> Exit ticket: one sentence — what trick did the fox play?</p>
  <h3 style="font-size: 0.85rem; font-weight: bold; text-transform: uppercase; letter-spacing: 0.05em; color: #7a6b62; margin-bottom: 0.5rem;">SLOs Addressed</h3>
  <p style="font-size: 0.875rem; color: #7a6b62;">R1.1 · R1.2 · R2.1 · R2.2</p>
</div>
`;

// ── UI primitives ─────────────────────────────────────────────────────────────

function Spinner() {
  return (
    <svg className="animate-spin h-5 w-5 text-dars-terra" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
    </svg>
  );
}

function ErrorMsg({ msg }: { msg: string }) {
  return (
    <p className="text-xs text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{msg}</p>
  );
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-4 py-2 text-sm font-semibold rounded-md transition-colors cursor-pointer border-none ${
        active
          ? "bg-dars-terra text-white"
          : "text-dars-muted hover:bg-dars-parchment-deep hover:text-dars-ink bg-transparent"
      }`}
    >
      {label}
    </button>
  );
}

// ── SLO Tracker (unchanged static) ───────────────────────────────────────────

type Subject = "English" | "Maths";

interface SubSlo {
  id: string;
  code: string;
  title: string;
  coverage: number;
  topics: string[];
}

interface Slo {
  id: string;
  code: string;
  title: string;
  subSlos: SubSlo[];
}

const SLOS: Record<Subject, Slo[]> = {
  English: [
    {
      id: "R1", code: "R1", title: "Read aloud with correct pronunciation and fluency",
      subSlos: [
        { id: "R1.1", code: "R1.1", title: "Reads with appropriate pace", coverage: 100, topics: ["Reading aloud"] },
        { id: "R1.2", code: "R1.2", title: "Uses correct stress and intonation", coverage: 75, topics: ["Reading aloud"] },
        { id: "R1.3", code: "R1.3", title: "Reads unfamiliar words using phonics", coverage: 33, topics: ["Vocabulary: cunning & sly"] },
        { id: "R1.4", code: "R1.4", title: "Reads with expression appropriate to punctuation", coverage: 50, topics: ["Direct speech", "Comprehension Q&A"] },
      ],
    },
    {
      id: "R2", code: "R2", title: "Demonstrate reading comprehension",
      subSlos: [
        { id: "R2.1", code: "R2.1", title: "Identifies the main idea of a passage", coverage: 100, topics: ["Comprehension Q&A", "Story sequencing", "Informational text"] },
        { id: "R2.2", code: "R2.2", title: "Answers literal comprehension questions", coverage: 80, topics: ["Comprehension Q&A", "Informational text", "Science non-fiction"] },
        { id: "R2.3", code: "R2.3", title: "Infers meaning from context", coverage: 40, topics: ["Vocabulary: cunning & sly", "Science non-fiction", "Fact vs. opinion"] },
        { id: "R2.4", code: "R2.4", title: "Identifies the main character and setting", coverage: 60, topics: ["Character analysis", "Story structure"] },
        { id: "R2.5", code: "R2.5", title: "Distinguishes fact from opinion", coverage: 30, topics: ["Fact vs. opinion", "Informational text"] },
        { id: "R2.6", code: "R2.6", title: "Sequences events from a story correctly", coverage: 70, topics: ["Story sequencing", "Story structure"] },
      ],
    },
    {
      id: "W1", code: "W1", title: "Write grammatically correct sentences",
      subSlos: [
        { id: "W1.1", code: "W1.1", title: "Uses correct punctuation", coverage: 25, topics: ["Direct speech", "Apostrophes"] },
        { id: "W1.2", code: "W1.2", title: "Applies subject-verb agreement", coverage: 0, topics: ["Past tense verbs", "Modal verbs"] },
        { id: "W1.3", code: "W1.3", title: "Uses appropriate vocabulary in writing", coverage: 50, topics: ["Vocabulary: cunning & sly", "Weather vocabulary"] },
      ],
    },
    {
      id: "W2", code: "W2", title: "Produce creative and descriptive writing",
      subSlos: [
        { id: "W2.1", code: "W2.1", title: "Writes a short story with beginning, middle, end", coverage: 0, topics: ["Story structure", "Creative writing"] },
        { id: "W2.2", code: "W2.2", title: "Uses descriptive adjectives and adverbs", coverage: 20, topics: ["Adjectives of emotion", "Similes & metaphors"] },
      ],
    },
  ],
  Maths: [
    {
      id: "N1", code: "N1", title: "Understand and work with whole numbers",
      subSlos: [
        { id: "N1.1", code: "N1.1", title: "Reads and writes numbers up to 1,000,000", coverage: 100, topics: ["Place value up to millions"] },
        { id: "N1.2", code: "N1.2", title: "Compares and orders large numbers", coverage: 100, topics: ["Comparing & ordering"] },
        { id: "N1.3", code: "N1.3", title: "Applies place value to round numbers", coverage: 100, topics: ["Place value up to millions", "Rounding numbers"] },
        { id: "N1.4", code: "N1.4", title: "Performs all four operations on whole numbers", coverage: 85, topics: ["Multi-step problems", "Mixed operations"] },
      ],
    },
    {
      id: "N2", code: "N2", title: "Perform operations with fractions",
      subSlos: [
        { id: "N2.1", code: "N2.1", title: "Adds and subtracts fractions with like denominators", coverage: 75, topics: ["Addition & subtraction"] },
        { id: "N2.2", code: "N2.2", title: "Multiplies a fraction by a whole number", coverage: 25, topics: ["Multiplication of decimals"] },
        { id: "N2.3", code: "N2.3", title: "Converts between mixed numbers and improper fractions", coverage: 0, topics: ["Mixed numbers"] },
      ],
    },
    {
      id: "G1", code: "G1", title: "Identify and describe 2D and 3D shapes",
      subSlos: [
        { id: "G1.1", code: "G1.1", title: "Names and draws common 2D shapes", coverage: 0, topics: ["2D shape properties"] },
        { id: "G1.2", code: "G1.2", title: "Identifies faces, edges, and vertices of 3D shapes", coverage: 0, topics: ["3D shape properties"] },
      ],
    },
  ],
};

function ringColor(pct: number) {
  if (pct === 0) return "#e0d5c8";
  if (pct === 100) return "#22c55e";
  if (pct >= 60) return "#f59e0b";
  return "#bf4e30";
}

function Ring({
  pct,
  r,
  stroke,
  children,
}: {
  pct: number;
  r: number;
  stroke: number;
  children?: React.ReactNode;
}) {
  const size = (r + stroke) * 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const color = ringColor(pct);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="block">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e0d5c8" strokeWidth={stroke} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={stroke}
        strokeDasharray={circ}
        strokeDashoffset={offset}
        strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 0.5s ease" }}
      />
      {children}
    </svg>
  );
}

function SloTab() {
  const [subject, setSubject] = useState<Subject>("English");
  const [activeSlo, setActiveSlo] = useState<string | null>(null);
  const slos = SLOS[subject];
  const allSubs = slos.flatMap((s) => s.subSlos);
  const overallPct = Math.round(
    allSubs.reduce((sum, ss) => sum + ss.coverage, 0) / allSubs.length
  );
  const fullyCovered = slos.filter((slo) => slo.subSlos.every((ss) => ss.coverage === 100)).length;
  const partiallyCovered = slos.filter(
    (slo) =>
      slo.subSlos.some((ss) => ss.coverage > 0) &&
      !slo.subSlos.every((ss) => ss.coverage === 100)
  ).length;
  const activeSloData = slos.find((s) => s.id === activeSlo) ?? null;

  return (
    <div>
      <div className="flex items-center gap-3 mb-6">
        <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg">
          {(["English", "Maths"] as Subject[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => {
                setSubject(s);
                setActiveSlo(null);
              }}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none ${
                subject === s
                  ? "bg-white text-dars-ink shadow-sm"
                  : "text-dars-muted bg-transparent hover:text-dars-ink"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-6 mb-8">
        <div className="relative shrink-0">
          <Ring pct={overallPct} r={36} stroke={6}>
            <text
              x="50%"
              y="50%"
              dominantBaseline="middle"
              textAnchor="middle"
              fontSize="13"
              fontWeight="bold"
              fill="#1c1410"
            >
              {overallPct}%
            </text>
          </Ring>
        </div>
        <div>
          <p className="text-base font-serif font-semibold text-dars-ink">
            Overall Curriculum Coverage
          </p>
          <p className="text-xs text-dars-muted mt-0.5">
            <span className="text-emerald-600 font-semibold">{fullyCovered}</span> SLOs complete
            &nbsp;·&nbsp;
            <span className="text-amber-600 font-semibold">{partiallyCovered}</span> in progress
            &nbsp;·&nbsp;
            <span className="font-semibold">{slos.length - fullyCovered - partiallyCovered}</span>{" "}
            not started
          </p>
          <div className="flex items-center gap-3 mt-2 text-[10px] text-dars-muted">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" /> Complete
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-amber-400" /> In progress
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-dars-terra" /> Started
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-full bg-dars-rule-light border border-dars-rule-dark" />{" "}
              Not started
            </span>
          </div>
        </div>
      </div>

      <div className="flex gap-6">
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest mb-4">
            Student Learning Outcomes
          </p>
          <div className="grid grid-cols-2 gap-3">
            {slos.map((slo) => {
              const sloPct = Math.round(
                slo.subSlos.reduce((s, ss) => s + ss.coverage, 0) / slo.subSlos.length
              );
              const isActive = activeSlo === slo.id;
              return (
                <button
                  key={slo.id}
                  type="button"
                  onClick={() => setActiveSlo(isActive ? null : slo.id)}
                  className={`text-left flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer bg-white ${
                    isActive
                      ? "border-dars-terra shadow-sm"
                      : "border-dars-rule-light hover:border-dars-muted-light"
                  }`}
                >
                  <div className="shrink-0">
                    <Ring pct={sloPct} r={22} stroke={5}>
                      <text
                        x="50%"
                        y="50%"
                        dominantBaseline="middle"
                        textAnchor="middle"
                        fontSize="9"
                        fontWeight="bold"
                        fill="#1c1410"
                      >
                        {sloPct}%
                      </text>
                    </Ring>
                  </div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold text-dars-muted uppercase tracking-wide">
                      {slo.code}
                    </p>
                    <p className="text-xs font-medium text-dars-ink leading-tight mt-0.5">
                      {slo.title}
                    </p>
                    <p className="text-[10px] text-dars-muted mt-1">
                      {slo.subSlos.length} sub-SLOs
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {activeSloData && (
          <div className="w-72 shrink-0 border border-dars-rule-light rounded-xl bg-dars-parchment p-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-[10px] font-bold text-dars-muted uppercase tracking-wide">
                {activeSloData.code}
              </span>
              <p className="text-sm font-serif font-semibold text-dars-ink leading-tight">
                {activeSloData.title}
              </p>
            </div>
            <div className="space-y-4">
              {activeSloData.subSlos.map((ss) => (
                <div key={ss.id}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Ring pct={ss.coverage} r={14} stroke={3.5}>
                      <text
                        x="50%"
                        y="50%"
                        dominantBaseline="middle"
                        textAnchor="middle"
                        fontSize="6.5"
                        fontWeight="bold"
                        fill="#1c1410"
                      >
                        {ss.coverage}
                      </text>
                    </Ring>
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold text-dars-muted">{ss.code}</p>
                      <p className="text-xs text-dars-ink leading-tight">{ss.title}</p>
                    </div>
                  </div>
                  {ss.topics.length > 0 && (
                    <div className="ml-9 flex flex-wrap gap-1">
                      {ss.topics.map((t) => (
                        <span key={t} className="text-[10px] text-dars-muted italic">
                          {t}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Setup Wizard ──────────────────────────────────────────────────────────────

interface WizardClassInput {
  grade: number;
  section: string;
}

interface WizardSubjectInput {
  classIdx: number;
  subject: string;
  teacherName: string;
}

interface WizardTimetableInput {
  classIdx: number;
  subjectIdx: number; // index in subjects array for that class
  days: number[]; // 0=Mon..5=Sat
}

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function SetupWizard({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1
  const [yearName, setYearName] = useState("");
  const [yearStart, setYearStart] = useState("");
  const [yearEnd, setYearEnd] = useState("");

  // Step 2
  const [holidays, setHolidays] = useState<{ name: string; date: string }[]>([]);
  const [holidayName, setHolidayName] = useState("");
  const [holidayDate, setHolidayDate] = useState("");

  // Step 3
  const [classes, setClasses] = useState<WizardClassInput[]>([{ grade: 5, section: "A" }]);

  // Step 4 — subjects per class
  const [subjects, setSubjects] = useState<WizardSubjectInput[]>([
    { classIdx: 0, subject: "", teacherName: "" },
  ]);

  // Step 5 — timetable per class-subject
  const [timetables, setTimetables] = useState<WizardTimetableInput[]>([]);

  // Initialise timetable state when entering step 5
  useEffect(() => {
    if (step === 5) {
      const tt: WizardTimetableInput[] = [];
      for (let ci = 0; ci < classes.length; ci++) {
        const classSubjects = subjects.filter((s) => s.classIdx === ci);
        for (let si = 0; si < classSubjects.length; si++) {
          const existing = timetables.find(
            (t) => t.classIdx === ci && t.subjectIdx === si
          );
          if (!existing) {
            tt.push({ classIdx: ci, subjectIdx: si, days: [] });
          } else {
            tt.push(existing);
          }
        }
      }
      setTimetables(tt);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step]);

  function toggleDay(ci: number, si: number, day: number) {
    setTimetables((prev) =>
      prev.map((t) => {
        if (t.classIdx !== ci || t.subjectIdx !== si) return t;
        const days = t.days.includes(day) ? t.days.filter((d) => d !== day) : [...t.days, day];
        return { ...t, days };
      })
    );
  }

  async function handleFinish() {
    setError(null);
    setSaving(true);
    try {
      // 1. Create academic year
      const year = await createAcademicYear({
        name: yearName,
        start_date: yearStart,
        end_date: yearEnd,
      });

      // 2. Holidays
      for (const h of holidays) {
        await addHoliday(year.id, { name: h.name, date: h.date });
      }

      // 3+4+5. Classes, subjects, timetables
      const createdClasses: { classId: string; cstIds: string[] }[] = [];

      for (let ci = 0; ci < classes.length; ci++) {
        const cls = classes[ci];
        const sc = await createClass({
          academic_year_id: year.id,
          grade: cls.grade,
          section: cls.section,
          name: `Grade ${cls.grade}-${cls.section}`,
        });

        const classSubjects = subjects.filter((s) => s.classIdx === ci);
        const cstIds: string[] = [];

        for (let si = 0; si < classSubjects.length; si++) {
          const sub = classSubjects[si];
          const cst = await assignSubject(sc.id, { subject: sub.subject });
          cstIds.push(cst.id);

          const tt = timetables.find((t) => t.classIdx === ci && t.subjectIdx === si);
          if (tt && tt.days.length > 0) {
            await setTimetable(sc.id, cst.id, {
              slots: tt.days.map((d) => ({ day_of_week: d })),
            });
          }
        }

        createdClasses.push({ classId: sc.id, cstIds });
      }

      onDone();
    } catch (e) {
      setError(e instanceof Error ? e.message : "An error occurred");
    } finally {
      setSaving(false);
    }
  }

  const totalSteps = 5;
  const stepLabels = ["Academic Year", "Holidays", "Classes", "Subjects", "Timetable"];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl mx-4 overflow-hidden">
        {/* Header */}
        <div className="bg-dars-ink px-6 py-5">
          <h2 className="text-lg font-serif font-bold text-white">School Setup</h2>
          <p className="text-xs text-dars-muted-light mt-0.5">
            Set up your school details to get started with the planner.
          </p>
        </div>

        {/* Step indicator */}
        <div className="flex items-center gap-0 px-6 py-4 border-b border-dars-rule-light bg-dars-parchment">
          {stepLabels.map((label, idx) => {
            const n = idx + 1;
            const done = n < step;
            const active = n === step;
            return (
              <div key={n} className="flex items-center">
                <div className="flex flex-col items-center gap-0.5">
                  <div
                    className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-bold ${
                      done
                        ? "bg-emerald-500 text-white"
                        : active
                        ? "bg-dars-terra text-white"
                        : "bg-dars-rule-light text-dars-muted"
                    }`}
                  >
                    {done ? "✓" : n}
                  </div>
                  <span
                    className={`text-[10px] font-medium ${
                      active ? "text-dars-terra" : "text-dars-muted"
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {idx < totalSteps - 1 && (
                  <div
                    className={`h-px w-8 mx-1 mb-3.5 ${
                      done ? "bg-emerald-400" : "bg-dars-rule-light"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>

        {/* Step content */}
        <div className="px-6 py-5 min-h-[240px]">
          {error && <ErrorMsg msg={error} />}

          {/* Step 1: Academic Year */}
          {step === 1 && (
            <div className="space-y-4">
              <p className="text-xs text-dars-muted font-semibold uppercase tracking-wide">
                Academic Year Details
              </p>
              <div>
                <label className="block text-xs font-semibold text-dars-muted mb-1">Name</label>
                <input
                  type="text"
                  placeholder="e.g. 2026-2027"
                  value={yearName}
                  onChange={(e) => setYearName(e.target.value)}
                  className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-dars-muted mb-1">
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={yearStart}
                    onChange={(e) => setYearStart(e.target.value)}
                    className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-dars-muted mb-1">
                    End Date
                  </label>
                  <input
                    type="date"
                    value={yearEnd}
                    onChange={(e) => setYearEnd(e.target.value)}
                    className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  />
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Holidays */}
          {step === 2 && (
            <div className="space-y-4">
              <p className="text-xs text-dars-muted font-semibold uppercase tracking-wide">
                Holidays (optional)
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  placeholder="Holiday name"
                  value={holidayName}
                  onChange={(e) => setHolidayName(e.target.value)}
                  className="flex-1 border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                />
                <input
                  type="date"
                  value={holidayDate}
                  onChange={(e) => setHolidayDate(e.target.value)}
                  className="border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                />
                <button
                  type="button"
                  onClick={() => {
                    if (holidayName && holidayDate) {
                      setHolidays((prev) => [...prev, { name: holidayName, date: holidayDate }]);
                      setHolidayName("");
                      setHolidayDate("");
                    }
                  }}
                  className="px-3 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 cursor-pointer border-none"
                >
                  Add
                </button>
              </div>
              {holidays.length === 0 ? (
                <p className="text-xs text-dars-muted italic">No holidays added yet.</p>
              ) : (
                <div className="space-y-1 max-h-40 overflow-y-auto">
                  {holidays.map((h, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between bg-dars-parchment border border-dars-rule-light rounded px-3 py-1.5 text-sm"
                    >
                      <span className="text-dars-ink">{h.name}</span>
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-dars-muted">{formatDateShort(h.date)}</span>
                        <button
                          type="button"
                          onClick={() => setHolidays((prev) => prev.filter((_, i) => i !== idx))}
                          className="text-dars-muted hover:text-red-600 cursor-pointer bg-transparent border-none text-xs"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Step 3: Classes */}
          {step === 3 && (
            <div className="space-y-4">
              <p className="text-xs text-dars-muted font-semibold uppercase tracking-wide">
                Classes
              </p>
              <div className="space-y-2">
                {classes.map((cls, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <div className="flex-1 grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-dars-muted mb-0.5">Grade</label>
                        <input
                          type="number"
                          min={1}
                          max={12}
                          value={cls.grade}
                          onChange={(e) => {
                            const val = Number(e.target.value);
                            setClasses((prev) =>
                              prev.map((c, i) => (i === idx ? { ...c, grade: val } : c))
                            );
                          }}
                          className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-dars-muted mb-0.5">Section</label>
                        <input
                          type="text"
                          placeholder="A"
                          value={cls.section}
                          onChange={(e) =>
                            setClasses((prev) =>
                              prev.map((c, i) =>
                                i === idx ? { ...c, section: e.target.value } : c
                              )
                            )
                          }
                          className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                        />
                      </div>
                    </div>
                    {classes.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          setClasses((prev) => prev.filter((_, i) => i !== idx));
                          setSubjects((prev) =>
                            prev
                              .filter((s) => s.classIdx !== idx)
                              .map((s) => ({
                                ...s,
                                classIdx: s.classIdx > idx ? s.classIdx - 1 : s.classIdx,
                              }))
                          );
                        }}
                        className="mt-4 text-dars-muted hover:text-red-600 cursor-pointer bg-transparent border-none text-sm"
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>
              <button
                type="button"
                onClick={() =>
                  setClasses((prev) => [...prev, { grade: 5, section: String.fromCharCode(65 + prev.length) }])
                }
                className="text-xs text-dars-terra font-semibold cursor-pointer bg-transparent border-none hover:underline"
              >
                + Add another class
              </button>
            </div>
          )}

          {/* Step 4: Subjects */}
          {step === 4 && (
            <div className="space-y-4">
              <p className="text-xs text-dars-muted font-semibold uppercase tracking-wide">
                Subjects (at least one per class)
              </p>
              {classes.map((cls, ci) => {
                const classSubjects = subjects.filter((s) => s.classIdx === ci);
                return (
                  <div key={ci} className="mb-3">
                    <p className="text-sm font-semibold text-dars-ink mb-2">
                      Grade {cls.grade}-{cls.section}
                    </p>
                    <div className="space-y-2 pl-3 border-l-2 border-dars-rule-light">
                      {classSubjects.map((sub, si) => {
                        const globalIdx = subjects.indexOf(sub);
                        return (
                          <div key={si} className="flex gap-2 items-end">
                            <div className="flex-1">
                              <label className="block text-xs text-dars-muted mb-0.5">
                                Subject name
                              </label>
                              <input
                                type="text"
                                placeholder="e.g. English"
                                value={sub.subject}
                                onChange={(e) =>
                                  setSubjects((prev) =>
                                    prev.map((s, i) =>
                                      i === globalIdx ? { ...s, subject: e.target.value } : s
                                    )
                                  )
                                }
                                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                              />
                            </div>
                            <div className="flex-1">
                              <label className="block text-xs text-dars-muted mb-0.5">
                                Teacher (optional)
                              </label>
                              <input
                                type="text"
                                placeholder="Teacher name"
                                value={sub.teacherName}
                                onChange={(e) =>
                                  setSubjects((prev) =>
                                    prev.map((s, i) =>
                                      i === globalIdx ? { ...s, teacherName: e.target.value } : s
                                    )
                                  )
                                }
                                className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                              />
                            </div>
                            {classSubjects.length > 1 && (
                              <button
                                type="button"
                                onClick={() =>
                                  setSubjects((prev) => prev.filter((_, i) => i !== globalIdx))
                                }
                                className="mb-0.5 text-dars-muted hover:text-red-600 cursor-pointer bg-transparent border-none text-sm"
                              >
                                ✕
                              </button>
                            )}
                          </div>
                        );
                      })}
                      <button
                        type="button"
                        onClick={() =>
                          setSubjects((prev) => [
                            ...prev,
                            { classIdx: ci, subject: "", teacherName: "" },
                          ])
                        }
                        className="text-xs text-dars-terra font-semibold cursor-pointer bg-transparent border-none hover:underline"
                      >
                        + Add subject
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Step 5: Timetable */}
          {step === 5 && (
            <div className="space-y-4">
              <p className="text-xs text-dars-muted font-semibold uppercase tracking-wide">
                Timetable (at least one day per subject)
              </p>
              {classes.map((cls, ci) => {
                const classSubjects = subjects.filter((s) => s.classIdx === ci);
                return (
                  <div key={ci} className="mb-3">
                    <p className="text-sm font-semibold text-dars-ink mb-2">
                      Grade {cls.grade}-{cls.section}
                    </p>
                    <div className="space-y-3 pl-3 border-l-2 border-dars-rule-light">
                      {classSubjects.map((sub, si) => {
                        const tt = timetables.find(
                          (t) => t.classIdx === ci && t.subjectIdx === si
                        );
                        return (
                          <div key={si}>
                            <p className="text-xs text-dars-muted mb-1.5">{sub.subject}</p>
                            <div className="flex gap-1.5 flex-wrap">
                              {DAY_LABELS.map((label, day) => {
                                const active = tt?.days.includes(day) ?? false;
                                return (
                                  <button
                                    key={day}
                                    type="button"
                                    onClick={() => toggleDay(ci, si, day)}
                                    className={`px-2.5 py-1 text-xs font-medium rounded-md border cursor-pointer transition-colors ${
                                      active
                                        ? "bg-dars-terra text-white border-dars-terra"
                                        : "bg-white text-dars-muted border-dars-rule-dark hover:border-dars-terra"
                                    }`}
                                  >
                                    {label}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer navigation */}
        <div className="px-6 py-4 border-t border-dars-rule-light flex items-center justify-between bg-dars-parchment">
          <button
            type="button"
            onClick={() => setStep((s) => Math.max(1, s - 1))}
            disabled={step === 1 || saving}
            className="px-4 py-2 text-sm font-semibold rounded-md border border-dars-rule-dark text-dars-muted hover:border-dars-ink hover:text-dars-ink transition-colors cursor-pointer bg-white disabled:opacity-40"
          >
            Back
          </button>
          <div className="flex items-center gap-3">
            {step === 2 && (
              <button
                type="button"
                onClick={() => setStep(3)}
                className="text-sm text-dars-muted hover:text-dars-ink cursor-pointer bg-transparent border-none"
              >
                Skip
              </button>
            )}
            {step < 5 ? (
              <button
                type="button"
                onClick={() => {
                  setError(null);
                  if (step === 1 && (!yearName || !yearStart || !yearEnd)) {
                    setError("Please fill in all academic year fields.");
                    return;
                  }
                  if (step === 3 && classes.some((c) => !c.section)) {
                    setError("Please fill in a section for each class.");
                    return;
                  }
                  if (
                    step === 4 &&
                    classes.some((_, ci) => {
                      const subs = subjects.filter((s) => s.classIdx === ci);
                      return subs.length === 0 || subs.some((s) => !s.subject);
                    })
                  ) {
                    setError("Each class needs at least one subject with a name.");
                    return;
                  }
                  setStep((s) => s + 1);
                }}
                className="px-5 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none"
              >
                Next
              </button>
            ) : (
              <button
                type="button"
                onClick={handleFinish}
                disabled={saving}
                className="px-5 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-60 flex items-center gap-2"
              >
                {saving && <Spinner />}
                Finish
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Today Tab ─────────────────────────────────────────────────────────────────

function TodayTab() {
  const [entries, setEntries] = useState<TodaySlotEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [marking, setMarking] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getToday();
      setEntries(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load today's schedule");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleMarkTaught(slotId: string) {
    setMarking(slotId);
    try {
      await markTaught(slotId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark slot as taught");
    } finally {
      setMarking(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 justify-center text-dars-muted">
        <Spinner />
        <span className="text-sm">Loading today&apos;s schedule…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-6">
        <ErrorMsg msg={error} />
      </div>
    );
  }

  if (entries.length === 0) {
    return (
      <div className="text-center py-16 text-dars-muted">
        <svg
          className="h-10 w-10 mx-auto mb-3 opacity-30"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        >
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
          <line x1="16" y1="2" x2="16" y2="6" />
          <line x1="8" y1="2" x2="8" y2="6" />
          <line x1="3" y1="10" x2="21" y2="10" />
        </svg>
        <p className="text-sm">No classes scheduled for today.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {entries.map((entry) => (
        <div
          key={`${entry.cst_id}`}
          className="bg-white border border-dars-rule-light rounded-xl p-5"
        >
          <div className="flex items-start justify-between mb-4">
            <div>
              <h3 className="text-base font-serif font-semibold text-dars-ink">
                {entry.class_name}
              </h3>
              <p className="text-xs text-dars-muted mt-0.5">
                {entry.subject}
                {entry.teacher_name && ` · ${entry.teacher_name}`}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {entry.previous_taught_slot && (
              <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-3">
                <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-wide mb-1">
                  Previous lesson
                </p>
                <p className="text-sm text-dars-ink">{entry.previous_taught_slot.title}</p>
              </div>
            )}
            {entry.next_planned_slot ? (
              <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-3">
                <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-wide mb-1">
                  Current lesson
                </p>
                <div className="flex items-center gap-2 mb-2">
                  <p className="text-sm text-dars-ink flex-1">{entry.next_planned_slot.title}</p>
                  <span
                    className={`text-[10px] font-semibold px-2 py-0.5 rounded shrink-0 ${
                      LP_TYPE_BADGE[entry.next_planned_slot.lp_type] ?? "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {entry.next_planned_slot.lp_type}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => void handleMarkTaught(entry.next_planned_slot!.id)}
                  disabled={marking === entry.next_planned_slot.id}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-600 text-white text-xs font-semibold rounded-md hover:opacity-90 cursor-pointer border-none disabled:opacity-60"
                >
                  {marking === entry.next_planned_slot.id && <Spinner />}
                  Mark as Taught
                </button>
              </div>
            ) : (
              <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-3">
                <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-wide mb-1">
                  Current lesson
                </p>
                <p className="text-xs text-dars-muted italic">No upcoming lesson slots.</p>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Classes Tab ───────────────────────────────────────────────────────────────

function ClassesTab({
  academicYearId,
  onViewSyllabus,
}: {
  academicYearId: string;
  onViewSyllabus: (classId: string, cstId: string) => void;
}) {
  const [classes, setClasses] = useState<SchoolClassRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeClassId, setActiveClassId] = useState<string | null>(null);
  const [classDetail, setClassDetail] = useState<SchoolClassWithSubjects | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getClasses(academicYearId)
      .then((res) => setClasses(res.items))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load classes"))
      .finally(() => setLoading(false));
  }, [academicYearId]);

  async function openClass(classId: string) {
    setActiveClassId(classId);
    setDetailLoading(true);
    try {
      const detail = await getClass(classId);
      setClassDetail(detail);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load class detail");
    } finally {
      setDetailLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 justify-center text-dars-muted">
        <Spinner />
        <span className="text-sm">Loading classes…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="py-6">
        <ErrorMsg msg={error} />
      </div>
    );
  }

  if (activeClassId && classDetail) {
    return (
      <div>
        <button
          type="button"
          onClick={() => {
            setActiveClassId(null);
            setClassDetail(null);
          }}
          className="flex items-center gap-1.5 text-sm text-dars-terra font-medium mb-5 cursor-pointer bg-transparent border-none hover:opacity-80"
        >
          <svg
            className="h-3.5 w-3.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
          >
            <polyline points="15 18 9 12 15 6" />
          </svg>
          All Classes
        </button>

        <div className="flex items-center gap-4 mb-6">
          <div>
            <h2 className="text-xl font-serif font-bold text-dars-ink">
              {classDetail.name}
            </h2>
            <p className="text-xs text-dars-muted mt-0.5">
              Grade {classDetail.grade}-{classDetail.section}
            </p>
          </div>
          <div className="ml-auto">
            <div className="text-center px-4 py-2 bg-dars-parchment border border-dars-rule-light rounded-lg">
              <p className="text-lg font-serif font-bold text-dars-ink">{classDetail.subjects.length}</p>
              <p className="text-[10px] text-dars-muted">Subjects</p>
            </div>
          </div>
        </div>

        {classDetail.subjects.length === 0 ? (
          <p className="text-sm text-dars-muted italic">No subjects assigned.</p>
        ) : (
          <div className="space-y-2">
            {classDetail.subjects.map((cst) => (
              <div
                key={cst.id}
                className="border border-dars-rule-light rounded-lg bg-white px-4 py-3 flex items-center justify-between"
              >
                <div>
                  <p className="text-sm font-semibold text-dars-ink">{cst.subject}</p>
                </div>
                <button
                  type="button"
                  onClick={() => onViewSyllabus(classDetail.id, cst.id)}
                  className="text-xs text-dars-terra font-medium hover:underline bg-transparent border-none cursor-pointer"
                >
                  View Chapter Plans →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  if (activeClassId && detailLoading) {
    return (
      <div className="flex items-center gap-2 py-12 justify-center text-dars-muted">
        <Spinner />
        <span className="text-sm">Loading class detail…</span>
      </div>
    );
  }

  if (classes.length === 0) {
    return (
      <div className="text-center py-16 text-dars-muted">
        <p className="text-sm">No classes found for this academic year.</p>
      </div>
    );
  }

  const grades = [...new Set(classes.map((c) => c.grade))].sort((a, b) => a - b);

  return (
    <div>
      {grades.map((grade) => (
        <div key={grade} className="mb-6">
          <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest mb-3">
            Grade {grade}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {classes
              .filter((c) => c.grade === grade)
              .map((c) => (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => void openClass(c.id)}
                  className="text-left bg-white border border-dars-rule-light rounded-xl p-4 hover:border-dars-terra hover:shadow-sm transition-all cursor-pointer"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="text-base font-serif font-semibold text-dars-ink">{c.name}</p>
                      <p className="text-xs text-dars-muted">
                        Grade {c.grade}-{c.section}
                      </p>
                    </div>
                  </div>
                  {c.start_date && (
                    <p className="text-xs text-dars-muted mt-2">
                      {formatDateShort(c.start_date)} – {formatDateShort(c.end_date)}
                    </p>
                  )}
                </button>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Syllabus Tab ──────────────────────────────────────────────────────────────

function SyllabusTab({
  classes,
  preselectedClassId,
  preselectedCstId,
}: {
  classes: SchoolClassRead[];
  preselectedClassId: string | null;
  preselectedCstId: string | null;
}) {
  const [selectedClassId, setSelectedClassId] = useState<string>(
    preselectedClassId ?? classes[0]?.id ?? ""
  );
  const [subjects, setSubjects] = useState<CSTRead[]>([]);
  const [selectedCstId, setSelectedCstId] = useState<string>(preselectedCstId ?? "");
  const [chapterPlans, setChapterPlans] = useState<ChapterPlanWithDates[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<"list" | "calendar">("list");
  const [schedulingFAs, setSchedulingFAs] = useState(false);

  // New chapter plan form
  const [showAddForm, setShowAddForm] = useState(false);
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [newChapterDays, setNewChapterDays] = useState(10);
  const [addingPlan, setAddingPlan] = useState(false);

  // Load subjects when class changes
  useEffect(() => {
    if (!selectedClassId) return;
    setError(null);
    const cls = classes.find((c) => c.id === selectedClassId);
    if (!cls) return;

    import("@/lib/school-api")
      .then((api) => api.getClass(selectedClassId))
      .then((detail) => {
        setSubjects(detail.subjects);
        if (preselectedCstId && detail.subjects.some((s) => s.id === preselectedCstId)) {
          setSelectedCstId(preselectedCstId);
        } else if (detail.subjects.length > 0) {
          setSelectedCstId(detail.subjects[0].id);
        } else {
          setSelectedCstId("");
        }
      })
      .catch((e: Error) => setError(e.message));
  }, [selectedClassId, classes, preselectedCstId]);

  // Load chapter plans when cst changes
  useEffect(() => {
    if (!selectedClassId || !selectedCstId) {
      setChapterPlans([]);
      return;
    }
    setLoading(true);
    setError(null);
    getChapterPlans(selectedClassId, selectedCstId)
      .then((res) => setChapterPlans(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedClassId, selectedCstId]);

  async function handleAutoSchedule() {
    if (!selectedClassId || !selectedCstId) return;
    setSchedulingFAs(true);
    setError(null);
    try {
      await autoScheduleFAs(selectedClassId, selectedCstId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auto-schedule failed");
    } finally {
      setSchedulingFAs(false);
    }
  }

  async function handleAddChapterPlan() {
    if (!selectedClassId || !selectedCstId || !newChapterTitle) return;
    setAddingPlan(true);
    setError(null);
    try {
      // Use a UUID-like chapter_id derived from title (backend doesn't have a chapter registry yet)
      const fakeChapterId = crypto.randomUUID();
      const res = await import("@/lib/school-api").then((api) =>
        api.upsertChapterPlans(selectedClassId, selectedCstId, {
          plans: [
            ...chapterPlans.map((p, i) => ({
              chapter_id: p.chapter_id,
              position: i + 1,
              teaching_days: p.teaching_days,
            })),
            {
              chapter_id: fakeChapterId,
              position: chapterPlans.length + 1,
              teaching_days: newChapterDays,
            },
          ],
        })
      );
      setChapterPlans(res.items);
      setNewChapterTitle("");
      setNewChapterDays(10);
      setShowAddForm(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add chapter plan");
    } finally {
      setAddingPlan(false);
    }
  }

  const today = new Date().toISOString().slice(0, 10);

  return (
    <div>
      {/* Selectors */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div>
          <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
            Class
          </label>
          <select
            value={selectedClassId}
            onChange={(e) => setSelectedClassId(e.target.value)}
            className="border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
            Subject
          </label>
          <select
            value={selectedCstId}
            onChange={(e) => setSelectedCstId(e.target.value)}
            disabled={subjects.length === 0}
            className="border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra disabled:opacity-60"
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.subject}
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg ml-auto">
          <button
            type="button"
            onClick={() => setView("list")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none flex items-center gap-1.5 ${
              view === "list"
                ? "bg-white text-dars-ink shadow-sm"
                : "text-dars-muted bg-transparent hover:text-dars-ink"
            }`}
          >
            <svg
              className="h-3.5 w-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <line x1="8" y1="6" x2="21" y2="6" />
              <line x1="8" y1="12" x2="21" y2="12" />
              <line x1="8" y1="18" x2="21" y2="18" />
              <line x1="3" y1="6" x2="3.01" y2="6" />
              <line x1="3" y1="12" x2="3.01" y2="12" />
              <line x1="3" y1="18" x2="3.01" y2="18" />
            </svg>
            List
          </button>
          <button
            type="button"
            onClick={() => setView("calendar")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none flex items-center gap-1.5 ${
              view === "calendar"
                ? "bg-white text-dars-ink shadow-sm"
                : "text-dars-muted bg-transparent hover:text-dars-ink"
            }`}
          >
            <svg
              className="h-3.5 w-3.5"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
              <line x1="16" y1="2" x2="16" y2="6" />
              <line x1="8" y1="2" x2="8" y2="6" />
              <line x1="3" y1="10" x2="21" y2="10" />
            </svg>
            Calendar
          </button>
        </div>
      </div>

      {error && <ErrorMsg msg={error} />}

      {loading ? (
        <div className="flex items-center gap-2 py-12 justify-center text-dars-muted">
          <Spinner />
          <span className="text-sm">Loading chapter plans…</span>
        </div>
      ) : chapterPlans.length === 0 ? (
        <div className="py-8">
          <p className="text-sm text-dars-muted mb-4">
            No chapter plans yet. Add them below.
          </p>
          {!showAddForm ? (
            <button
              type="button"
              onClick={() => setShowAddForm(true)}
              className="px-4 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 cursor-pointer border-none"
            >
              + Add Chapter Plan
            </button>
          ) : (
            <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-4 max-w-md">
              <div className="flex gap-3 mb-3">
                <div className="flex-1">
                  <label className="block text-xs font-semibold text-dars-muted mb-1">
                    Chapter title
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. The Clever Fox"
                    value={newChapterTitle}
                    onChange={(e) => setNewChapterTitle(e.target.value)}
                    className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-dars-muted mb-1">
                    Teaching days
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={60}
                    value={newChapterDays}
                    onChange={(e) => setNewChapterDays(Number(e.target.value))}
                    className="w-24 border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void handleAddChapterPlan()}
                  disabled={addingPlan || !newChapterTitle}
                  className="px-4 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 cursor-pointer border-none disabled:opacity-60 flex items-center gap-2"
                >
                  {addingPlan && <Spinner />}
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="px-4 py-2 text-sm font-semibold rounded-md border border-dars-rule-dark text-dars-muted hover:text-dars-ink cursor-pointer bg-white"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <>
          {/* Action bar */}
          <div className="flex items-center justify-between mb-4">
            <p className="text-xs text-dars-muted">
              {chapterPlans.length} chapters &nbsp;·&nbsp;{" "}
              {chapterPlans.reduce((s, c) => s + c.teaching_days, 0)} teaching days planned
            </p>
            <button
              type="button"
              onClick={() => void handleAutoSchedule()}
              disabled={schedulingFAs}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-dars-terra border border-dars-terra rounded-md hover:bg-dars-terra hover:text-white transition-colors cursor-pointer bg-white disabled:opacity-60"
            >
              {schedulingFAs && <Spinner />}
              + Auto-schedule FAs
            </button>
          </div>

          {view === "list" ? (
            <div className="space-y-2">
              {chapterPlans.map((ch, i) => {
                const isPast = ch.end_date !== null && ch.end_date < today;
                const isActive =
                  ch.start_date !== null &&
                  ch.end_date !== null &&
                  ch.start_date <= today &&
                  ch.end_date >= today;
                const color = CHAPTER_COLORS[i % CHAPTER_COLORS.length];
                return (
                  <div
                    key={ch.id}
                    className={`border rounded-lg px-4 py-3 flex items-center gap-4 ${
                      isPast
                        ? "opacity-60 bg-dars-parchment"
                        : "bg-white border-dars-rule-light"
                    }`}
                  >
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded border ${color} shrink-0`}
                    >
                      Ch {ch.position}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p
                        className={`text-sm font-semibold ${
                          isPast ? "text-dars-muted" : "text-dars-ink"
                        }`}
                      >
                        Chapter {ch.position}
                      </p>
                      <p className="text-xs text-dars-muted">
                        {formatDateShort(ch.start_date)} – {formatDateShort(ch.end_date)} &nbsp;·&nbsp;{" "}
                        {ch.teaching_days} teaching days
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {isActive && (
                        <span className="text-[10px] font-semibold tracking-wide uppercase bg-dars-terra text-white px-1.5 py-0.5 rounded">
                          Current
                        </span>
                      )}
                      {isPast && (
                        <span className="text-[10px] font-semibold tracking-wide uppercase bg-dars-parchment-deep text-dars-muted px-1.5 py-0.5 rounded">
                          Done
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <SyllabusCalendarView plans={chapterPlans} />
          )}

          <div className="mt-4">
            {!showAddForm ? (
              <button
                type="button"
                onClick={() => setShowAddForm(true)}
                className="text-xs text-dars-terra font-semibold cursor-pointer bg-transparent border-none hover:underline"
              >
                + Add chapter plan
              </button>
            ) : (
              <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-4 max-w-md mt-2">
                <div className="flex gap-3 mb-3">
                  <div className="flex-1">
                    <label className="block text-xs font-semibold text-dars-muted mb-1">
                      Chapter title
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. The Clever Fox"
                      value={newChapterTitle}
                      onChange={(e) => setNewChapterTitle(e.target.value)}
                      className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-dars-muted mb-1">
                      Teaching days
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={60}
                      value={newChapterDays}
                      onChange={(e) => setNewChapterDays(Number(e.target.value))}
                      className="w-24 border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
                    />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => void handleAddChapterPlan()}
                    disabled={addingPlan || !newChapterTitle}
                    className="px-4 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 cursor-pointer border-none disabled:opacity-60 flex items-center gap-2"
                  >
                    {addingPlan && <Spinner />}
                    Save
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowAddForm(false)}
                    className="px-4 py-2 text-sm font-semibold rounded-md border border-dars-rule-dark text-dars-muted hover:text-dars-ink cursor-pointer bg-white"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function SyllabusCalendarView({ plans }: { plans: ChapterPlanWithDates[] }) {
  // Build month grid from earliest start_date to latest end_date
  const starts = plans.map((p) => p.start_date).filter(Boolean) as string[];
  const ends = plans.map((p) => p.end_date).filter(Boolean) as string[];
  if (starts.length === 0 || ends.length === 0) {
    return <p className="text-sm text-dars-muted italic">Date ranges not available.</p>;
  }

  const minDate = new Date(starts.sort()[0] + "T00:00:00");
  const maxDate = new Date(ends.sort().reverse()[0] + "T00:00:00");

  // Map each date to chapter index
  const dayToChapter: Record<string, number> = {};
  plans.forEach((plan, idx) => {
    if (!plan.start_date || !plan.end_date) return;
    let cur = new Date(plan.start_date + "T00:00:00");
    const end = new Date(plan.end_date + "T00:00:00");
    while (cur <= end) {
      dayToChapter[cur.toISOString().slice(0, 10)] = idx;
      cur = new Date(cur.getTime() + 86400000);
    }
  });

  const months: { year: number; month: number }[] = [];
  let cur = new Date(minDate.getFullYear(), minDate.getMonth(), 1);
  const endMonth = new Date(maxDate.getFullYear(), maxDate.getMonth(), 1);
  while (cur <= endMonth) {
    months.push({ year: cur.getFullYear(), month: cur.getMonth() });
    cur = new Date(cur.getFullYear(), cur.getMonth() + 1, 1);
  }

  return (
    <div className="space-y-6">
      {months.map(({ year, month }) => {
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const firstDow = new Date(year, month, 1).getDay();
        const cells: (number | null)[] = Array(firstDow).fill(null);
        for (let d = 1; d <= daysInMonth; d++) cells.push(d);
        while (cells.length % 7 !== 0) cells.push(null);

        const monthLabel = new Date(year, month, 1).toLocaleString("en", { month: "long" });
        const mStart = `${year}-${String(month + 1).padStart(2, "0")}-01`;
        const mEnd = `${year}-${String(month + 1).padStart(2, "0")}-${String(daysInMonth).padStart(2, "0")}`;

        return (
          <div key={`${year}-${month}`}>
            <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest mb-2">
              {monthLabel} {year}
            </p>
            <div className="grid grid-cols-7 gap-px bg-dars-rule-light rounded-lg overflow-hidden text-center text-[11px]">
              {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                <div key={i} className="bg-dars-parchment py-1 font-semibold text-dars-muted">
                  {d}
                </div>
              ))}
              {cells.map((day, i) => {
                if (!day) return <div key={i} className="bg-white py-1.5" />;
                const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const chIdx = dayToChapter[iso];
                const dow = new Date(iso + "T00:00:00").getDay();
                const isWeekend = dow === 0 || dow === 6;
                const colorClass =
                  chIdx !== undefined
                    ? CHAPTER_COLORS[chIdx % CHAPTER_COLORS.length].split(" ")[0]
                    : "";
                return (
                  <div
                    key={i}
                    title={chIdx !== undefined ? `Ch ${plans[chIdx]?.position}: ${plans[chIdx]?.teaching_days} days` : ""}
                    className={`py-1.5 ${
                      isWeekend
                        ? "bg-dars-parchment text-dars-muted/40"
                        : chIdx !== undefined
                        ? `${colorClass} text-gray-800 font-medium`
                        : "bg-white text-dars-ink"
                    }`}
                  >
                    {day}
                  </div>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-2 mt-2">
              {plans.map((plan, idx) => {
                if (!plan.start_date || !plan.end_date) return null;
                if (plan.start_date > mEnd || plan.end_date < mStart) return null;
                return (
                  <span
                    key={plan.id}
                    className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${CHAPTER_COLORS[idx % CHAPTER_COLORS.length]}`}
                  >
                    Ch {plan.position}: {plan.teaching_days} days
                  </span>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Lesson Breakdown Tab ──────────────────────────────────────────────────────

function LessonsTab({ classes }: { classes: SchoolClassRead[] }) {
  const [selectedClassId, setSelectedClassId] = useState<string>(classes[0]?.id ?? "");
  const [subjects, setSubjects] = useState<CSTRead[]>([]);
  const [selectedCstId, setSelectedCstId] = useState<string>("");
  const [chapterPlans, setChapterPlans] = useState<ChapterPlanWithDates[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string>("");
  const [slots, setSlots] = useState<ClassLessonSlotRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [viewedLP, setViewedLP] = useState<string | null>(null);
  const [marking, setMarking] = useState<string | null>(null);

  // Load subjects on class change
  useEffect(() => {
    if (!selectedClassId) return;
    import("@/lib/school-api")
      .then((api) => api.getClass(selectedClassId))
      .then((detail) => {
        setSubjects(detail.subjects);
        if (detail.subjects.length > 0) setSelectedCstId(detail.subjects[0].id);
        else setSelectedCstId("");
      })
      .catch(() => {});
  }, [selectedClassId]);

  // Load chapter plans on cst change
  useEffect(() => {
    if (!selectedClassId || !selectedCstId) {
      setChapterPlans([]);
      setSelectedPlanId("");
      return;
    }
    getChapterPlans(selectedClassId, selectedCstId)
      .then((res) => {
        setChapterPlans(res.items);
        if (res.items.length > 0) setSelectedPlanId(res.items[0].id);
        else setSelectedPlanId("");
      })
      .catch(() => {});
  }, [selectedClassId, selectedCstId]);

  // Load lesson slots on plan change
  useEffect(() => {
    if (!selectedPlanId) {
      setSlots([]);
      return;
    }
    setLoading(true);
    setError(null);
    getLessonSlots(selectedPlanId)
      .then((res) => setSlots(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedPlanId]);

  async function handleGenerate() {
    if (!selectedPlanId) return;
    setGenerating(true);
    setError(null);
    try {
      const res = await generateLessonSlots(selectedPlanId);
      setSlots(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed");
    } finally {
      setGenerating(false);
    }
  }

  async function handleMarkTaught(slotId: string) {
    setMarking(slotId);
    try {
      const updated = await markTaught(slotId);
      setSlots((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to mark slot as taught");
    } finally {
      setMarking(null);
    }
  }

  return (
    <div>
      {/* Selectors */}
      <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-5 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
              Class
            </label>
            <select
              value={selectedClassId}
              onChange={(e) => setSelectedClassId(e.target.value)}
              className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
            >
              {classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
              Subject
            </label>
            <select
              value={selectedCstId}
              onChange={(e) => setSelectedCstId(e.target.value)}
              disabled={subjects.length === 0}
              className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra disabled:opacity-60"
            >
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.subject}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
              Chapter Plan
            </label>
            <select
              value={selectedPlanId}
              onChange={(e) => setSelectedPlanId(e.target.value)}
              disabled={chapterPlans.length === 0}
              className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra disabled:opacity-60"
            >
              {chapterPlans.map((p, i) => (
                <option key={p.id} value={p.id}>
                  Chapter {p.position} ({p.teaching_days} days)
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <ErrorMsg msg={error} />
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-12 justify-center text-dars-muted">
          <Spinner />
          <span className="text-sm">Loading lesson slots…</span>
        </div>
      ) : slots.length === 0 ? (
        <div className="text-center py-12">
          <svg
            className="h-10 w-10 mx-auto mb-3 opacity-30 text-dars-muted"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2" />
            <rect x="9" y="3" width="6" height="4" rx="1" />
            <line x1="9" y1="12" x2="15" y2="12" />
            <line x1="9" y1="16" x2="12" y2="16" />
          </svg>
          <p className="text-sm text-dars-muted mb-4">
            No lesson slots yet for this chapter plan.
          </p>
          {selectedPlanId && (
            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={generating}
              className="px-5 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 cursor-pointer border-none disabled:opacity-60 flex items-center gap-2 mx-auto"
            >
              {generating && <Spinner />}
              Generate Lesson Breakdown
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {slots.map((slot) => (
            <div key={slot.id}>
              <div className="border border-dars-rule-light rounded-lg bg-white px-4 py-3 flex items-center gap-4">
                <span className="text-xs font-bold text-dars-muted w-6 shrink-0">
                  {slot.day_number}
                </span>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-dars-ink">{slot.title}</p>
                </div>
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded shrink-0 ${
                    LP_TYPE_BADGE[slot.lp_type] ?? "bg-gray-100 text-gray-700"
                  }`}
                >
                  {slot.lp_type}
                </span>
                {slot.status === "taught" && (
                  <span className="text-[10px] font-semibold tracking-wide uppercase bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded shrink-0">
                    Taught
                  </span>
                )}
                {slot.status === "planned" && (
                  <button
                    type="button"
                    onClick={() => void handleMarkTaught(slot.id)}
                    disabled={marking === slot.id}
                    className="shrink-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-emerald-600 text-white rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none disabled:opacity-60"
                  >
                    {marking === slot.id && <Spinner />}
                    Mark Taught
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setViewedLP(viewedLP === slot.id ? null : slot.id)}
                  className="shrink-0 px-3 py-1.5 text-xs font-semibold border border-dars-terra text-dars-terra rounded-md hover:bg-dars-terra hover:text-white transition-colors cursor-pointer bg-transparent"
                >
                  {viewedLP === slot.id ? "Close" : "View LP"}
                </button>
              </div>

              {viewedLP === slot.id && (
                <div className="border border-t-0 border-dars-rule-light rounded-b-lg bg-white px-6 py-5">
                  <div className="flex items-center justify-between mb-4">
                    <h4 className="text-sm font-serif font-semibold text-dars-ink">
                      Lesson Plan Preview
                    </h4>
                    <span className="text-[10px] font-semibold tracking-wide uppercase bg-dars-parchment-deep text-dars-muted px-2 py-0.5 rounded">
                      Sample
                    </span>
                  </div>
                  <div
                    className="prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: SAMPLE_LP_HTML }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Assessments Tab ───────────────────────────────────────────────────────────

function AssessmentsTab({ classes }: { classes: SchoolClassRead[] }) {
  const [selectedClassId, setSelectedClassId] = useState<string>(classes[0]?.id ?? "");
  const [subjects, setSubjects] = useState<CSTRead[]>([]);
  const [selectedCstId, setSelectedCstId] = useState<string>("");
  const [slots, setSlots] = useState<AssessmentSlotRead[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);

  // Load subjects on class change
  useEffect(() => {
    if (!selectedClassId) return;
    import("@/lib/school-api")
      .then((api) => api.getClass(selectedClassId))
      .then((detail) => {
        setSubjects(detail.subjects);
        if (detail.subjects.length > 0) setSelectedCstId(detail.subjects[0].id);
        else setSelectedCstId("");
      })
      .catch(() => {});
  }, [selectedClassId]);

  // Load assessment slots on cst change
  useEffect(() => {
    if (!selectedClassId || !selectedCstId) {
      setSlots([]);
      return;
    }
    setLoading(true);
    setError(null);
    getAssessmentSlots(selectedClassId, selectedCstId)
      .then((res) => setSlots(res.items))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [selectedClassId, selectedCstId]);

  async function handleStatusChange(slotId: string, newStatus: string) {
    setUpdating(slotId);
    try {
      const updated = await updateAssessmentSlot(slotId, { status: newStatus });
      setSlots((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update status");
    } finally {
      setUpdating(null);
    }
  }

  return (
    <div>
      {/* Selectors */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        <div>
          <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
            Class
          </label>
          <select
            value={selectedClassId}
            onChange={(e) => setSelectedClassId(e.target.value)}
            className="border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
          >
            {classes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
            Subject
          </label>
          <select
            value={selectedCstId}
            onChange={(e) => setSelectedCstId(e.target.value)}
            disabled={subjects.length === 0}
            className="border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra disabled:opacity-60"
          >
            {subjects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.subject}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <ErrorMsg msg={error} />
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-12 justify-center text-dars-muted">
          <Spinner />
          <span className="text-sm">Loading assessments…</span>
        </div>
      ) : slots.length === 0 ? (
        <div className="text-center py-16 text-dars-muted">
          <svg
            className="h-10 w-10 mx-auto mb-3 opacity-30"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M9 11l3 3L22 4" />
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
          </svg>
          <p className="text-sm">
            No assessments scheduled. Use Auto-schedule FAs in the Syllabus tab.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="bg-dars-parchment">
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide border-b border-dars-rule-light">
                  Chapter
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide border-b border-dars-rule-light">
                  Type
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide border-b border-dars-rule-light">
                  Scheduled Date
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide border-b border-dars-rule-light">
                  Title
                </th>
                <th className="text-left px-4 py-2.5 text-xs font-semibold text-dars-muted uppercase tracking-wide border-b border-dars-rule-light">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {slots.map((slot) => (
                <tr key={slot.id} className="border-b border-dars-rule-light hover:bg-dars-parchment/40">
                  <td className="px-4 py-3 text-xs text-dars-muted">
                    {slot.chapter_plan_id ? slot.chapter_plan_id.slice(0, 8) + "…" : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                        slot.assessment_type === "FA"
                          ? "bg-blue-100 text-blue-800"
                          : "bg-violet-100 text-violet-800"
                      }`}
                    >
                      {slot.assessment_type}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-dars-ink">
                    {formatDate(slot.scheduled_date)}
                  </td>
                  <td className="px-4 py-3 text-sm text-dars-ink">{slot.title ?? "—"}</td>
                  <td className="px-4 py-3">
                    <select
                      value={slot.status}
                      onChange={(e) => void handleStatusChange(slot.id, e.target.value)}
                      disabled={updating === slot.id}
                      className="border border-dars-rule-dark rounded px-2 py-1 text-xs text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra disabled:opacity-60"
                    >
                      <option value="scheduled">Scheduled</option>
                      <option value="completed">Completed</option>
                      <option value="skipped">Skipped</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "today" | "classes" | "syllabus" | "lessons" | "slos" | "assessments";

export default function CurriculumPage() {
  const [tab, setTab] = useState<Tab>("today");
  const [academicYear, setAcademicYear] = useState<AcademicYearRead | null>(null);
  const [classes, setClasses] = useState<SchoolClassRead[]>([]);
  const [showWizard, setShowWizard] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(true);
  const [bootstrapError, setBootstrapError] = useState<string | null>(null);

  // Syllabus deep-link state (set when clicking "View Chapter Plans" from Classes tab)
  const [syllabusClassId, setSyllabusClassId] = useState<string | null>(null);
  const [syllabusCstId, setSyllabusCstId] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    setBootstrapping(true);
    setBootstrapError(null);
    try {
      const years = await getAcademicYears();
      if (years.items.length === 0) {
        setShowWizard(true);
        setBootstrapping(false);
        return;
      }
      const year = years.items[0];
      setAcademicYear(year);
      const cls = await getClasses(year.id);
      setClasses(cls.items);
    } catch (e) {
      setBootstrapError(e instanceof Error ? e.message : "Failed to load school data");
    } finally {
      setBootstrapping(false);
    }
  }, []);

  useEffect(() => {
    void bootstrap();
  }, [bootstrap]);

  function handleWizardDone() {
    setShowWizard(false);
    void bootstrap();
  }

  function handleViewSyllabus(classId: string, cstId: string) {
    setSyllabusClassId(classId);
    setSyllabusCstId(cstId);
    setTab("syllabus");
  }

  if (bootstrapping) {
    return (
      <div className="p-8 flex items-center gap-2 text-dars-muted">
        <Spinner />
        <span className="text-sm">Loading planner…</span>
      </div>
    );
  }

  if (bootstrapError) {
    return (
      <div className="p-8">
        <ErrorMsg msg={bootstrapError} />
        <button
          type="button"
          onClick={() => void bootstrap()}
          className="mt-3 px-4 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md cursor-pointer border-none"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <>
      {showWizard && <SetupWizard onDone={handleWizardDone} />}

      <div className="p-8 max-w-5xl">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-2xl font-serif font-bold text-dars-ink">Curriculum Planner</h1>
          <p className="text-sm text-dars-muted mt-1">
            {academicYear ? academicYear.name : "No academic year configured"}
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-dars-rule-light pb-3 flex-wrap">
          <TabButton label="Today" active={tab === "today"} onClick={() => setTab("today")} />
          <TabButton label="Classes" active={tab === "classes"} onClick={() => setTab("classes")} />
          <TabButton
            label="Syllabus"
            active={tab === "syllabus"}
            onClick={() => setTab("syllabus")}
          />
          <TabButton
            label="Lesson Breakdown"
            active={tab === "lessons"}
            onClick={() => setTab("lessons")}
          />
          <TabButton
            label="SLO Tracker"
            active={tab === "slos"}
            onClick={() => setTab("slos")}
          />
          <TabButton
            label="Assessments"
            active={tab === "assessments"}
            onClick={() => setTab("assessments")}
          />
        </div>

        {/* Tab content */}
        {tab === "today" && <TodayTab />}
        {tab === "classes" && academicYear && (
          <ClassesTab
            academicYearId={academicYear.id}
            onViewSyllabus={handleViewSyllabus}
          />
        )}
        {tab === "syllabus" && (
          <SyllabusTab
            classes={classes}
            preselectedClassId={syllabusClassId}
            preselectedCstId={syllabusCstId}
          />
        )}
        {tab === "lessons" && <LessonsTab classes={classes} />}
        {tab === "slos" && <SloTab />}
        {tab === "assessments" && <AssessmentsTab classes={classes} />}
      </div>
    </>
  );
}
