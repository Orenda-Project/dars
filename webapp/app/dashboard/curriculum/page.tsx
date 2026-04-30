"use client";

import { useState } from "react";

// ── Static Data ───────────────────────────────────────────────────────────────

type Subject = "English" | "Maths";

const HOLIDAYS = new Set([
  "2026-05-01", // Labour Day
  "2026-06-05", "2026-06-06", "2026-06-07", "2026-06-08", "2026-06-09", "2026-06-10", "2026-06-11", "2026-06-12", "2026-06-13", "2026-06-14", // Summer break
  "2026-08-14", // Independence Day
  "2026-09-14", "2026-09-15", "2026-09-16", // Eid Milad
  "2026-11-09", // Iqbal Day
  "2026-12-21", "2026-12-22", "2026-12-23", "2026-12-24", "2026-12-25", "2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31",
  "2027-01-01", // Winter break
  "2027-02-15", "2027-02-16", "2027-02-17", "2027-02-18", "2027-02-19", // Mid-year exams
  "2027-03-23", // Pakistan Day
]);

function isWeekend(date: Date) {
  const d = date.getDay();
  return d === 0 || d === 6;
}

function isHoliday(date: Date) {
  return HOLIDAYS.has(date.toISOString().slice(0, 10));
}

function isTeachingDay(date: Date) {
  return !isWeekend(date) && !isHoliday(date);
}

function addDays(date: Date, n: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + n);
  return d;
}

function toISO(date: Date) {
  return date.toISOString().slice(0, 10);
}

// Build ordered teaching days for the academic year Apr 2026 – Mar 2027
function buildTeachingDays(): string[] {
  const days: string[] = [];
  let cur = new Date("2026-04-01");
  const end = new Date("2027-03-31");
  while (cur <= end) {
    if (isTeachingDay(cur)) days.push(toISO(cur));
    cur = addDays(cur, 1);
  }
  return days;
}

const TEACHING_DAYS = buildTeachingDays();

interface Chapter {
  id: string;
  title: string;
  days: number; // teaching days allocated
}

const ENGLISH_CHAPTERS: Chapter[] = [
  { id: "en1", title: "The Clever Fox", days: 14 },
  { id: "en2", title: "A Day at the Farm", days: 12 },
  { id: "en3", title: "The Lost Kite", days: 14 },
  { id: "en4", title: "Seasons of Pakistan", days: 10 },
  { id: "en5", title: "The Brave Little Tailor", days: 15 },
  { id: "en6", title: "My Neighbourhood", days: 10 },
  { id: "en7", title: "Water — A Precious Gift", days: 12 },
  { id: "en8", title: "The Magic Paintbrush", days: 14 },
  { id: "en9", title: "Our Earth, Our Home", days: 11 },
  { id: "en10", title: "The Postman's Round", days: 13 },
  { id: "en11", title: "Stars and Planets", days: 12 },
  { id: "en12", title: "Revision & Assessment", days: 10 },
];

const MATHS_CHAPTERS: Chapter[] = [
  { id: "ma1", title: "Whole Numbers", days: 18 },
  { id: "ma2", title: "Fractions", days: 20 },
  { id: "ma3", title: "Decimals", days: 16 },
  { id: "ma4", title: "Percentages", days: 12 },
  { id: "ma5", title: "Measurement", days: 14 },
  { id: "ma6", title: "Geometry — Shapes", days: 16 },
  { id: "ma7", title: "Area & Perimeter", days: 14 },
  { id: "ma8", title: "Data Handling", days: 12 },
  { id: "ma9", title: "Word Problems", days: 16 },
  { id: "ma10", title: "Revision & Assessment", days: 10 },
];

const LP_TYPES: Record<Subject, string[]> = {
  English: ["Reading", "Comprehension — Word Meanings", "Comprehension — Q&A", "Grammar", "Creative Writing", "Revision"],
  Maths: ["Concrete", "Pictorial & Abstract", "Word Problems", "Revision"],
};

// Distribute LP types across N lessons for a subject
function generateLessonSequence(subject: Subject, chapter: Chapter, count: number) {
  const types = LP_TYPES[subject];
  const lessons = [];
  for (let i = 0; i < count; i++) {
    let lpType: string;
    if (i === count - 1) {
      lpType = "Revision";
    } else if (subject === "English") {
      const cycle = ["Reading", "Comprehension — Word Meanings", "Comprehension — Q&A", "Grammar", "Creative Writing"];
      lpType = cycle[i % cycle.length];
    } else {
      const cycle = ["Concrete", "Pictorial & Abstract", "Word Problems"];
      lpType = cycle[i % cycle.length];
    }
    lessons.push({
      id: `${chapter.id}-l${i + 1}`,
      number: i + 1,
      lpType,
      title: `${lpType}: ${chapter.title}`,
      viewed: i < 3, // first 3 are "already viewed" for demo
    });
  }
  return lessons;
}

// Sub-SLO coverage is 0–100 (% of lessons touching this sub-SLO that have been viewed)
interface SubSlo {
  id: string;
  code: string;
  title: string;
  coverage: number; // 0–100
  topics: string[]; // chapter topic titles that address this sub-SLO
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
        { id: "R1.1", code: "R1.1", title: "Reads with appropriate pace",                      coverage: 100, topics: ["Reading aloud"] },
        { id: "R1.2", code: "R1.2", title: "Uses correct stress and intonation",                coverage: 75,  topics: ["Reading aloud"] },
        { id: "R1.3", code: "R1.3", title: "Reads unfamiliar words using phonics",              coverage: 33,  topics: ["Vocabulary: cunning & sly"] },
        { id: "R1.4", code: "R1.4", title: "Reads with expression appropriate to punctuation",  coverage: 50,  topics: ["Direct speech", "Comprehension Q&A"] },
      ],
    },
    {
      id: "R2", code: "R2", title: "Demonstrate reading comprehension",
      subSlos: [
        { id: "R2.1", code: "R2.1", title: "Identifies the main idea of a passage",             coverage: 100, topics: ["Comprehension Q&A", "Story sequencing", "Informational text"] },
        { id: "R2.2", code: "R2.2", title: "Answers literal comprehension questions",           coverage: 80,  topics: ["Comprehension Q&A", "Informational text", "Science non-fiction"] },
        { id: "R2.3", code: "R2.3", title: "Infers meaning from context",                       coverage: 40,  topics: ["Vocabulary: cunning & sly", "Science non-fiction", "Fact vs. opinion"] },
        { id: "R2.4", code: "R2.4", title: "Identifies the main character and setting",         coverage: 60,  topics: ["Character analysis", "Story structure"] },
        { id: "R2.5", code: "R2.5", title: "Distinguishes fact from opinion",                   coverage: 30,  topics: ["Fact vs. opinion", "Informational text"] },
        { id: "R2.6", code: "R2.6", title: "Sequences events from a story correctly",           coverage: 70,  topics: ["Story sequencing", "Story structure"] },
      ],
    },
    {
      id: "R3", code: "R3", title: "Expand vocabulary through reading",
      subSlos: [
        { id: "R3.1", code: "R3.1", title: "Uses context clues to determine word meaning",      coverage: 55,  topics: ["Vocabulary: cunning & sly", "Weather vocabulary", "Science vocabulary"] },
        { id: "R3.2", code: "R3.2", title: "Identifies synonyms and antonyms",                  coverage: 40,  topics: ["Vocabulary: cunning & sly", "Farm animals vocabulary"] },
        { id: "R3.3", code: "R3.3", title: "Understands subject-specific vocabulary",           coverage: 35,  topics: ["Science vocabulary", "Community vocabulary", "Environmental vocabulary"] },
      ],
    },
    {
      id: "W1", code: "W1", title: "Write grammatically correct sentences",
      subSlos: [
        { id: "W1.1", code: "W1.1", title: "Uses correct punctuation",                          coverage: 25,  topics: ["Direct speech", "Apostrophes"] },
        { id: "W1.2", code: "W1.2", title: "Applies subject-verb agreement",                    coverage: 0,   topics: ["Past tense verbs", "Modal verbs"] },
        { id: "W1.3", code: "W1.3", title: "Uses appropriate vocabulary in writing",            coverage: 50,  topics: ["Vocabulary: cunning & sly", "Weather vocabulary"] },
        { id: "W1.4", code: "W1.4", title: "Writes compound and complex sentences",             coverage: 20,  topics: ["Connectives", "Conjunctions"] },
        { id: "W1.5", code: "W1.5", title: "Uses correct verb tenses consistently",             coverage: 15,  topics: ["Past tense verbs", "Present perfect tense", "Modal verbs"] },
      ],
    },
    {
      id: "W2", code: "W2", title: "Produce creative and descriptive writing",
      subSlos: [
        { id: "W2.1", code: "W2.1", title: "Writes a short story with beginning, middle, end",  coverage: 0,   topics: ["Story structure", "Creative writing"] },
        { id: "W2.2", code: "W2.2", title: "Uses descriptive adjectives and adverbs",           coverage: 20,  topics: ["Adjectives of emotion", "Similes & metaphors"] },
        { id: "W2.3", code: "W2.3", title: "Uses similes and metaphors effectively",            coverage: 10,  topics: ["Similes & metaphors", "Descriptive writing"] },
        { id: "W2.4", code: "W2.4", title: "Organises writing with clear paragraphs",           coverage: 0,   topics: ["Creative writing", "Persuasive writing"] },
      ],
    },
    {
      id: "W3", code: "W3", title: "Write for different purposes and audiences",
      subSlos: [
        { id: "W3.1", code: "W3.1", title: "Writes a structured informal letter",               coverage: 45,  topics: ["Letter writing"] },
        { id: "W3.2", code: "W3.2", title: "Writes persuasive text with reasons",               coverage: 0,   topics: ["Persuasive writing"] },
        { id: "W3.3", code: "W3.3", title: "Writes factual descriptions of places or events",   coverage: 30,  topics: ["Descriptive writing", "Environmental vocabulary"] },
      ],
    },
    {
      id: "L1", code: "L1", title: "Apply knowledge of grammar and language structure",
      subSlos: [
        { id: "L1.1", code: "L1.1", title: "Identifies and uses prepositions correctly",        coverage: 60,  topics: ["Prepositions of place", "Map reading"] },
        { id: "L1.2", code: "L1.2", title: "Uses modal verbs to express possibility/obligation",coverage: 20,  topics: ["Modal verbs"] },
        { id: "L1.3", code: "L1.3", title: "Applies connectives to join clauses",               coverage: 35,  topics: ["Connectives", "Conjunctions"] },
        { id: "L1.4", code: "L1.4", title: "Uses apostrophes for possession and contraction",   coverage: 25,  topics: ["Apostrophes"] },
        { id: "L1.5", code: "L1.5", title: "Punctuates direct speech correctly",                coverage: 30,  topics: ["Direct speech"] },
      ],
    },
  ],
  Maths: [
    {
      id: "N1", code: "N1", title: "Understand and work with whole numbers",
      subSlos: [
        { id: "N1.1", code: "N1.1", title: "Reads and writes numbers up to 1,000,000",          coverage: 100, topics: ["Place value up to millions"] },
        { id: "N1.2", code: "N1.2", title: "Compares and orders large numbers",                  coverage: 100, topics: ["Comparing & ordering"] },
        { id: "N1.3", code: "N1.3", title: "Applies place value to round numbers",               coverage: 100, topics: ["Place value up to millions", "Rounding numbers"] },
        { id: "N1.4", code: "N1.4", title: "Performs all four operations on whole numbers",      coverage: 85,  topics: ["Multi-step problems", "Mixed operations"] },
      ],
    },
    {
      id: "N2", code: "N2", title: "Perform operations with fractions",
      subSlos: [
        { id: "N2.1", code: "N2.1", title: "Adds and subtracts fractions with like denominators",coverage: 75,  topics: ["Addition & subtraction"] },
        { id: "N2.2", code: "N2.2", title: "Multiplies a fraction by a whole number",            coverage: 25,  topics: ["Multiplication of decimals"] },
        { id: "N2.3", code: "N2.3", title: "Converts between mixed numbers and improper fractions",coverage: 0, topics: ["Mixed numbers"] },
        { id: "N2.4", code: "N2.4", title: "Identifies equivalent fractions",                    coverage: 50,  topics: ["Equivalent fractions"] },
      ],
    },
    {
      id: "N3", code: "N3", title: "Understand and apply decimals and percentages",
      subSlos: [
        { id: "N3.1", code: "N3.1", title: "Reads and writes decimals to hundredths",            coverage: 60,  topics: ["Decimal place value"] },
        { id: "N3.2", code: "N3.2", title: "Multiplies and divides decimals by 10 and 100",      coverage: 40,  topics: ["Multiplication of decimals", "Division of decimals"] },
        { id: "N3.3", code: "N3.3", title: "Calculates percentage of a quantity",                coverage: 20,  topics: ["Percent of a quantity"] },
        { id: "N3.4", code: "N3.4", title: "Converts between fractions, decimals, percentages",  coverage: 0,   topics: ["Converting fractions to %", "Decimal place value"] },
      ],
    },
    {
      id: "G1", code: "G1", title: "Identify and describe 2D and 3D shapes",
      subSlos: [
        { id: "G1.1", code: "G1.1", title: "Names and draws common 2D shapes",                   coverage: 0,   topics: ["2D shape properties"] },
        { id: "G1.2", code: "G1.2", title: "Identifies faces, edges, and vertices of 3D shapes", coverage: 0,   topics: ["3D shape properties"] },
        { id: "G1.3", code: "G1.3", title: "Classifies angles as acute, obtuse, or right",       coverage: 0,   topics: ["Angles"] },
        { id: "G1.4", code: "G1.4", title: "Identifies lines of symmetry in 2D shapes",          coverage: 0,   topics: ["2D shape properties"] },
      ],
    },
    {
      id: "G2", code: "G2", title: "Calculate area, perimeter, and volume",
      subSlos: [
        { id: "G2.1", code: "G2.1", title: "Calculates perimeter of rectangles and polygons",    coverage: 0,   topics: ["Perimeter of polygons"] },
        { id: "G2.2", code: "G2.2", title: "Calculates area of rectangles and triangles",        coverage: 0,   topics: ["Area of rectangles", "Area of triangles"] },
        { id: "G2.3", code: "G2.3", title: "Distinguishes between area and perimeter",           coverage: 0,   topics: ["Area & Perimeter"] },
      ],
    },
    {
      id: "M1", code: "M1", title: "Apply measurement concepts",
      subSlos: [
        { id: "M1.1", code: "M1.1", title: "Converts between units of length, mass, capacity",   coverage: 0,   topics: ["Units of length", "Units of mass", "Units of capacity"] },
        { id: "M1.2", code: "M1.2", title: "Solves real-world measurement problems",             coverage: 0,   topics: ["Real-world problems", "Multi-step problems"] },
        { id: "M1.3", code: "M1.3", title: "Reads and interprets data from charts and graphs",   coverage: 0,   topics: ["Tally charts", "Bar graphs", "Pie charts"] },
        { id: "M1.4", code: "M1.4", title: "Constructs bar graphs and tally charts",             coverage: 0,   topics: ["Bar graphs", "Tally charts"] },
      ],
    },
    {
      id: "P1", code: "P1", title: "Apply problem-solving strategies",
      subSlos: [
        { id: "P1.1", code: "P1.1", title: "Identifies relevant information in word problems",   coverage: 55,  topics: ["Word Problems", "Multi-step problems"] },
        { id: "P1.2", code: "P1.2", title: "Selects and applies appropriate operations",         coverage: 40,  topics: ["Mixed operations", "Problem-solving strategies"] },
        { id: "P1.3", code: "P1.3", title: "Checks reasonableness of answers",                   coverage: 20,  topics: ["Problem-solving strategies", "Mental maths"] },
        { id: "P1.4", code: "P1.4", title: "Solves multi-step word problems",                    coverage: 30,  topics: ["Multi-step problems", "Real-world problems"] },
      ],
    },
  ],
};

// Map topic title → sub-SLO ids (derived from SLOS for Books tab linkage)
function buildTopicToSubSlos(): Record<string, string[]> {
  const map: Record<string, string[]> = {};
  for (const slos of Object.values(SLOS)) {
    for (const slo of slos) {
      for (const ss of slo.subSlos) {
        for (const topic of ss.topics) {
          if (!map[topic]) map[topic] = [];
          map[topic].push(ss.id);
        }
      }
    }
  }
  return map;
}

const TOPIC_TO_SUBSLOS = buildTopicToSubSlos();

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

// ── Helpers ───────────────────────────────────────────────────────────────────

function chapterDateRanges(chapters: Chapter[]): { start: string; end: string }[] {
  const ranges: { start: string; end: string }[] = [];
  let cursor = 0;
  for (const ch of chapters) {
    const startIdx = cursor;
    const endIdx = Math.min(cursor + ch.days - 1, TEACHING_DAYS.length - 1);
    ranges.push({ start: TEACHING_DAYS[startIdx] ?? "", end: TEACHING_DAYS[endIdx] ?? "" });
    cursor += ch.days;
  }
  return ranges;
}

function formatDate(iso: string) {
  if (!iso) return "—";
  return new Date(iso + "T00:00:00").toLocaleDateString("en-PK", { day: "numeric", month: "short" });
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

// ── Sub-components ────────────────────────────────────────────────────────────

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
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

// ── Tab 1: Syllabus ───────────────────────────────────────────────────────────

function SyllabusTab() {
  const [subject, setSubject] = useState<Subject>("English");
  const [view, setView] = useState<"list" | "calendar">("list");
  const chapters = subject === "English" ? ENGLISH_CHAPTERS : MATHS_CHAPTERS;
  const ranges = chapterDateRanges(chapters);

  return (
    <div>
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3 mb-6">
        <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg">
          {(["English", "Maths"] as Subject[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSubject(s)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none ${
                subject === s ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg ml-auto">
          <button
            type="button"
            onClick={() => setView("list")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none flex items-center gap-1.5 ${
              view === "list" ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"
            }`}
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
            List
          </button>
          <button
            type="button"
            onClick={() => setView("calendar")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none flex items-center gap-1.5 ${
              view === "calendar" ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"
            }`}
          >
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>
            Calendar
          </button>
        </div>
      </div>

      <p className="text-xs text-dars-muted mb-5">
        Academic Year: Apr 2026 – Mar 2027 &nbsp;·&nbsp; {TEACHING_DAYS.length} teaching days &nbsp;·&nbsp; {chapters.reduce((s, c) => s + c.days, 0)} days planned
      </p>

      {view === "list" ? (
        <SyllabusListView chapters={chapters} ranges={ranges} subject={subject} />
      ) : (
        <SyllabusCalendarView chapters={chapters} subject={subject} />
      )}
    </div>
  );
}

function SyllabusListView({ chapters, ranges, subject }: { chapters: Chapter[]; ranges: { start: string; end: string }[]; subject: Subject }) {
  const today = toISO(new Date());

  return (
    <div className="space-y-2">
      {chapters.map((ch, i) => {
        const isPast = ranges[i].end < today;
        const isActive = ranges[i].start <= today && ranges[i].end >= today;
        const color = CHAPTER_COLORS[i % CHAPTER_COLORS.length];

        return (
          <div
            key={ch.id}
            className={`border rounded-lg px-4 py-3 flex items-center gap-4 ${
              isPast ? "opacity-60 bg-dars-parchment" : "bg-white border-dars-rule-light"
            }`}
          >
            <span className={`text-xs font-bold px-2 py-0.5 rounded border ${color} shrink-0`}>
              Ch {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-semibold ${isPast ? "text-dars-muted" : "text-dars-ink"}`}>{ch.title}</p>
              <p className="text-xs text-dars-muted">
                {formatDate(ranges[i].start)} – {formatDate(ranges[i].end)} &nbsp;·&nbsp; {ch.days} teaching days
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
              {!isPast && (
                <a
                  href={`/dashboard/curriculum?tab=lessons&subject=${subject}&chapter=${ch.id}`}
                  className="text-xs text-dars-terra font-medium hover:underline no-underline"
                >
                  View Lessons →
                </a>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function SyllabusCalendarView({ chapters, subject }: { chapters: Chapter[]; subject: Subject }) {
  // Build a month grid for Apr 2026 – Mar 2027
  const months: { label: string; year: number; month: number }[] = [];
  for (let m = 3; m <= 11; m++) months.push({ label: new Date(2026, m, 1).toLocaleString("en", { month: "long" }), year: 2026, month: m });
  for (let m = 0; m <= 2; m++) months.push({ label: new Date(2027, m, 1).toLocaleString("en", { month: "long" }), year: 2027, month: m });

  // Map each teaching day to its chapter index
  const ranges = chapterDateRanges(chapters);
  const dayToChapter: Record<string, number> = {};
  ranges.forEach(({ start, end }, idx) => {
    let cur = new Date(start + "T00:00:00");
    const endDate = new Date(end + "T00:00:00");
    while (cur <= endDate) {
      dayToChapter[toISO(cur)] = idx;
      cur = addDays(cur, 1);
    }
  });

  return (
    <div className="space-y-6">
      {months.map(({ label, year, month }) => {
        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const firstDow = new Date(year, month, 1).getDay(); // 0=Sun

        const cells: (number | null)[] = Array(firstDow).fill(null);
        for (let d = 1; d <= daysInMonth; d++) cells.push(d);
        while (cells.length % 7 !== 0) cells.push(null);

        return (
          <div key={`${year}-${month}`}>
            <p className="text-xs font-semibold text-dars-muted uppercase tracking-widest mb-2">{label} {year}</p>
            <div className="grid grid-cols-7 gap-px bg-dars-rule-light rounded-lg overflow-hidden text-center text-[11px]">
              {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
                <div key={i} className="bg-dars-parchment py-1 font-semibold text-dars-muted">{d}</div>
              ))}
              {cells.map((day, i) => {
                if (!day) return <div key={i} className="bg-white py-1.5" />;
                const iso = `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
                const chIdx = dayToChapter[iso];
                const isOff = isWeekend(new Date(iso + "T00:00:00")) || isHoliday(new Date(iso + "T00:00:00"));
                const colorClass = chIdx !== undefined ? CHAPTER_COLORS[chIdx % CHAPTER_COLORS.length].split(" ")[0] : "";

                return (
                  <div
                    key={i}
                    title={chIdx !== undefined ? `Ch ${chIdx + 1}: ${chapters[chIdx]?.title}` : isOff ? "Non-teaching day" : ""}
                    className={`py-1.5 ${isOff ? "bg-dars-parchment text-dars-muted/40" : chIdx !== undefined ? `${colorClass} text-gray-800 font-medium` : "bg-white text-dars-ink"}`}
                  >
                    {day}
                  </div>
                );
              })}
            </div>
            {/* Legend for chapters visible in this month */}
            <div className="flex flex-wrap gap-2 mt-2">
              {chapters.map((ch, idx) => {
                const r = ranges[idx];
                const mStart = `${year}-${String(month + 1).padStart(2, "0")}-01`;
                const mEnd = `${year}-${String(month + 1).padStart(2, "0")}-${String(daysInMonth).padStart(2, "0")}`;
                if (r.start > mEnd || r.end < mStart) return null;
                return (
                  <span key={ch.id} className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${CHAPTER_COLORS[idx % CHAPTER_COLORS.length]}`}>
                    Ch {idx + 1}: {ch.title}
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

// ── Tab 2: Lesson Chunking ────────────────────────────────────────────────────

function LessonsTab() {
  const [subject, setSubject] = useState<Subject>("English");
  const [chapterId, setChapterId] = useState<string>("en1");
  const [lessonCount, setLessonCount] = useState<number>(10);
  const [lessons, setLessons] = useState<ReturnType<typeof generateLessonSequence> | null>(null);
  const [viewedLP, setViewedLP] = useState<string | null>(null);

  const chapters = subject === "English" ? ENGLISH_CHAPTERS : MATHS_CHAPTERS;
  const chapter = chapters.find((c) => c.id === chapterId) ?? chapters[0];

  function handleSubjectChange(s: Subject) {
    setSubject(s);
    const newChapters = s === "English" ? ENGLISH_CHAPTERS : MATHS_CHAPTERS;
    setChapterId(newChapters[0].id);
    setLessons(null);
    setViewedLP(null);
  }

  function handleGenerate() {
    setLessons(generateLessonSequence(subject, chapter, lessonCount));
    setViewedLP(null);
  }

  const lpTypeBadgeColor: Record<string, string> = {
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

  return (
    <div>
      {/* Setup form */}
      <div className="bg-dars-parchment border border-dars-rule-light rounded-lg p-5 mb-6">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">Subject</label>
            <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg">
              {(["English", "Maths"] as Subject[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => handleSubjectChange(s)}
                  className={`flex-1 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none ${
                    subject === s ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">Chapter</label>
            <select
              value={chapterId}
              onChange={(e) => { setChapterId(e.target.value); setLessons(null); setViewedLP(null); }}
              className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
            >
              {chapters.map((ch) => (
                <option key={ch.id} value={ch.id}>{ch.title}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-dars-muted mb-1 uppercase tracking-wide">
              Number of Lessons
            </label>
            <input
              type="number"
              min={2}
              max={20}
              value={lessonCount}
              onChange={(e) => setLessonCount(Number(e.target.value))}
              className="w-full border border-dars-rule-dark rounded-md px-3 py-2 text-sm text-dars-ink bg-white focus:outline-none focus:ring-1 focus:ring-dars-terra"
            />
          </div>
        </div>
        <button
          type="button"
          onClick={handleGenerate}
          className="px-5 py-2 bg-dars-terra text-white text-sm font-semibold rounded-md hover:opacity-90 transition-opacity cursor-pointer border-none"
        >
          Generate Lesson Breakdown
        </button>
      </div>

      {/* Lesson sequence */}
      {lessons && (
        <>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-serif font-semibold text-dars-ink">
              {chapter.title} — {lessons.length} Lessons
            </h3>
            <p className="text-xs text-dars-muted">{subject} · Grade 5</p>
          </div>

          <div className="space-y-2 mb-6">
            {lessons.map((lesson) => (
              <div key={lesson.id}>
                <div className="border border-dars-rule-light rounded-lg bg-white px-4 py-3 flex items-center gap-4">
                  <span className="text-xs font-bold text-dars-muted w-6 shrink-0">{lesson.number}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-dars-ink">{lesson.title}</p>
                  </div>
                  <span className={`text-[10px] font-semibold px-2 py-0.5 rounded ${lpTypeBadgeColor[lesson.lpType] ?? "bg-gray-100 text-gray-700"} shrink-0`}>
                    {lesson.lpType}
                  </span>
                  {lesson.viewed && (
                    <span className="text-[10px] font-semibold tracking-wide uppercase bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded shrink-0">
                      Viewed
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setViewedLP(viewedLP === lesson.id ? null : lesson.id)}
                    className="shrink-0 px-3 py-1.5 text-xs font-semibold border border-dars-terra text-dars-terra rounded-md hover:bg-dars-terra hover:text-white transition-colors cursor-pointer bg-transparent"
                  >
                    {viewedLP === lesson.id ? "Close" : "View Lesson"}
                  </button>
                </div>

                {/* LP preview expands inline beneath each row */}
                {viewedLP === lesson.id && (
                  <div className="border border-t-0 border-dars-rule-light rounded-b-lg bg-white px-6 py-5">
                    <div className="flex items-center justify-between mb-4">
                      <h4 className="text-sm font-serif font-semibold text-dars-ink">Lesson Plan Preview</h4>
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
        </>
      )}

      {!lessons && (
        <div className="text-center py-16 text-dars-muted">
          <svg className="h-10 w-10 mx-auto mb-3 opacity-30" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="12" y2="16"/></svg>
          <p className="text-sm">Select a chapter and click Generate to see the lesson breakdown.</p>
        </div>
      )}
    </div>
  );
}

// ── Ring helpers ─────────────────────────────────────────────────────────────

function ringColor(pct: number) {
  if (pct === 0)   return "#e0d5c8"; // dars-rule-light — not started
  if (pct === 100) return "#22c55e"; // emerald-500 — complete
  if (pct >= 60)   return "#f59e0b"; // amber-400 — good progress
  return "#bf4e30";                  // dars-terra — started but low
}

function Ring({ pct, r, stroke, children }: { pct: number; r: number; stroke: number; children?: React.ReactNode }) {
  const size = (r + stroke) * 2;
  const circ = 2 * Math.PI * r;
  const offset = circ * (1 - pct / 100);
  const color = ringColor(pct);

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="block">
      {/* Track */}
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e0d5c8" strokeWidth={stroke} />
      {/* Progress */}
      <circle
        cx={size / 2} cy={size / 2} r={r}
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

// ── Tab 3: SLO Tracker ────────────────────────────────────────────────────────

// ── SLO Tree View ─────────────────────────────────────────────────────────────

function SloTreeView({ slos }: { slos: Slo[] }) {
  return (
    <div className="space-y-6">
      {slos.map((slo) => {
        const sloPct = Math.round(slo.subSlos.reduce((s, ss) => s + ss.coverage, 0) / slo.subSlos.length);
        return (
          <div key={slo.id} className="flex gap-4">
            {/* Parent node */}
            <div className="flex flex-col items-center">
              <div className="flex flex-col items-center bg-white border border-dars-rule-light rounded-xl px-4 py-3 w-40 shrink-0 shadow-sm">
                <Ring pct={sloPct} r={24} stroke={5}>
                  <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="10" fontWeight="bold" fill="#1c1410">
                    {sloPct}%
                  </text>
                </Ring>
                <p className="text-[10px] font-bold text-dars-muted uppercase tracking-wide mt-2">{slo.code}</p>
                <p className="text-xs font-medium text-dars-ink text-center leading-tight mt-0.5">{slo.title}</p>
              </div>
            </div>

            {/* Connector + children */}
            <div className="flex items-stretch gap-0 pt-4">
              {/* Vertical + horizontal connector lines */}
              <div className="flex flex-col justify-around w-6 shrink-0">
                {slo.subSlos.map((ss, i) => (
                  <div key={ss.id} className="flex items-center h-full">
                    <div className="w-full border-t-2 border-dars-rule-light" />
                  </div>
                ))}
              </div>
              {/* Vertical spine */}
              <div className="w-px bg-dars-rule-light self-stretch" />
            </div>

            {/* Child nodes */}
            <div className="flex flex-col justify-around gap-2 py-1">
              {slo.subSlos.map((ss) => (
                <div key={ss.id} className="flex items-center gap-3 bg-dars-parchment border border-dars-rule-light rounded-lg px-3 py-2">
                  <Ring pct={ss.coverage} r={16} stroke={4}>
                    <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="7" fontWeight="bold" fill="#1c1410">
                      {ss.coverage}
                    </text>
                  </Ring>
                  <div>
                    <p className="text-[10px] font-bold text-dars-muted">{ss.code}</p>
                    <p className="text-xs text-dars-ink leading-tight">{ss.title}</p>
                    {ss.topics.length > 0 && (
                      <p className="text-[10px] text-dars-muted italic mt-0.5">{ss.topics.join(" · ")}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── Tab 3: SLO Tracker ────────────────────────────────────────────────────────

function SloTab() {
  const [subject, setSubject] = useState<Subject>("English");
  const [activeSlo, setActiveSlo] = useState<string | null>(null);
  const [view, setView] = useState<"map" | "tree">("map");
  const slos = SLOS[subject];

  // Overall coverage = mean of all sub-SLO coverages
  const allSubs = slos.flatMap((s) => s.subSlos);
  const overallPct = Math.round(allSubs.reduce((sum, ss) => sum + ss.coverage, 0) / allSubs.length);
  const fullyCovered = slos.filter((slo) => slo.subSlos.every((ss) => ss.coverage === 100)).length;
  const partiallyCovered = slos.filter((slo) => slo.subSlos.some((ss) => ss.coverage > 0) && !slo.subSlos.every((ss) => ss.coverage === 100)).length;

  const activeSloData = slos.find((s) => s.id === activeSlo) ?? null;

  return (
    <div>
      {/* Controls row */}
      <div className="flex items-center gap-3 mb-6">
        <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg">
          {(["English", "Maths"] as Subject[]).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => { setSubject(s); setActiveSlo(null); }}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none ${
                subject === s ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex gap-1 p-1 bg-dars-parchment-deep rounded-lg ml-auto">
          <button type="button" onClick={() => setView("map")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none flex items-center gap-1.5 ${view === "map" ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"}`}>
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="6" cy="6" r="2"/><circle cx="18" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/></svg>
            Map
          </button>
          <button type="button" onClick={() => setView("tree")}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors cursor-pointer border-none flex items-center gap-1.5 ${view === "tree" ? "bg-white text-dars-ink shadow-sm" : "text-dars-muted bg-transparent hover:text-dars-ink"}`}>
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></svg>
            Tree
          </button>
        </div>
      </div>

      {/* Summary strip */}
      <div className="flex items-center gap-6 mb-8">
        {/* Overall ring */}
        <div className="relative shrink-0">
          <Ring pct={overallPct} r={36} stroke={6}>
            <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="13" fontWeight="bold" fill="#1c1410">
              {overallPct}%
            </text>
          </Ring>
        </div>
        <div>
          <p className="text-base font-serif font-semibold text-dars-ink">Overall Curriculum Coverage</p>
          <p className="text-xs text-dars-muted mt-0.5">
            <span className="text-emerald-600 font-semibold">{fullyCovered}</span> SLOs complete &nbsp;·&nbsp;
            <span className="text-amber-600 font-semibold">{partiallyCovered}</span> in progress &nbsp;·&nbsp;
            <span className="font-semibold">{slos.length - fullyCovered - partiallyCovered}</span> not started
          </p>
          <div className="flex items-center gap-3 mt-2 text-[10px] text-dars-muted">
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-emerald-500" /> Complete</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-amber-400" /> In progress</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-dars-terra" /> Started</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full bg-dars-rule-light border border-dars-rule-dark" /> Not started</span>
          </div>
        </div>
      </div>

      {/* Tree view */}
      {view === "tree" && <SloTreeView slos={slos} />}

      {/* Map view */}
      {view === "map" && <div className="flex gap-6">
        {/* SLO ring map */}
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest mb-4">Student Learning Outcomes</p>
          <div className="grid grid-cols-2 gap-3">
            {slos.map((slo) => {
              const sloPct = Math.round(slo.subSlos.reduce((s, ss) => s + ss.coverage, 0) / slo.subSlos.length);
              const isActive = activeSlo === slo.id;
              return (
                <button
                  key={slo.id}
                  type="button"
                  onClick={() => setActiveSlo(isActive ? null : slo.id)}
                  className={`text-left flex items-center gap-3 p-3 rounded-xl border transition-all cursor-pointer bg-white ${
                    isActive ? "border-dars-terra shadow-sm" : "border-dars-rule-light hover:border-dars-muted-light"
                  }`}
                >
                  <div className="shrink-0">
                    <Ring pct={sloPct} r={22} stroke={5}>
                      <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="9" fontWeight="bold" fill="#1c1410">
                        {sloPct}%
                      </text>
                    </Ring>
                  </div>
                  <div className="min-w-0">
                    <p className="text-[10px] font-bold text-dars-muted uppercase tracking-wide">{slo.code}</p>
                    <p className="text-xs font-medium text-dars-ink leading-tight mt-0.5">{slo.title}</p>
                    <p className="text-[10px] text-dars-muted mt-1">{slo.subSlos.length} sub-SLOs</p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Sub-SLO detail panel */}
        {activeSloData && (
          <div className="w-72 shrink-0 border border-dars-rule-light rounded-xl bg-dars-parchment p-4">
            <div className="flex items-center gap-2 mb-4">
              <span className="text-[10px] font-bold text-dars-muted uppercase tracking-wide">{activeSloData.code}</span>
              <p className="text-sm font-serif font-semibold text-dars-ink leading-tight">{activeSloData.title}</p>
            </div>
            <div className="space-y-4">
              {activeSloData.subSlos.map((ss) => (
                <div key={ss.id}>
                  <div className="flex items-center gap-2 mb-1.5">
                    <Ring pct={ss.coverage} r={14} stroke={3.5}>
                      <text x="50%" y="50%" dominantBaseline="middle" textAnchor="middle" fontSize="6.5" fontWeight="bold" fill="#1c1410">
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
                        <span key={t} className="text-[10px] text-dars-muted italic">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>}
    </div>
  );
}

// ── Static Book Data ──────────────────────────────────────────────────────────

interface BookChapter {
  number: number;
  title: string;
  pages: string; // e.g. "1–18"
  topics: string[];
}

interface Book {
  id: string;
  title: string;
  subject: Subject;
  grade: string;
  publisher: string;
  edition: string;
  totalPages: number;
  chapters: BookChapter[];
}

const BOOKS: Book[] = [
  {
    id: "eng5",
    title: "New Countdown English 5",
    subject: "English",
    grade: "5",
    publisher: "Oxford University Press",
    edition: "3rd Edition",
    totalPages: 196,
    chapters: [
      { number: 1,  title: "The Clever Fox",           pages: "1–16",   topics: ["Reading aloud", "Vocabulary: cunning & sly", "Comprehension Q&A"] },
      { number: 2,  title: "A Day at the Farm",         pages: "17–30",  topics: ["Descriptive writing", "Farm animals vocabulary", "Past tense verbs"] },
      { number: 3,  title: "The Lost Kite",             pages: "31–46",  topics: ["Story sequencing", "Adjectives of emotion", "Direct speech"] },
      { number: 4,  title: "Seasons of Pakistan",       pages: "47–58",  topics: ["Informational text", "Weather vocabulary", "Compare & contrast"] },
      { number: 5,  title: "The Brave Little Tailor",   pages: "59–76",  topics: ["Character analysis", "Dialogue writing", "Connectives"] },
      { number: 6,  title: "My Neighbourhood",          pages: "77–88",  topics: ["Community vocabulary", "Map reading", "Prepositions of place"] },
      { number: 7,  title: "Water — A Precious Gift",   pages: "89–102", topics: ["Science non-fiction", "Cause and effect", "Modal verbs"] },
      { number: 8,  title: "The Magic Paintbrush",      pages: "103–118",topics: ["Creative writing", "Similes & metaphors", "Story structure"] },
      { number: 9,  title: "Our Earth, Our Home",       pages: "119–130",topics: ["Environmental vocabulary", "Persuasive writing", "Conjunctions"] },
      { number: 10, title: "The Postman's Round",       pages: "131–144",topics: ["Community helpers", "Letter writing", "Apostrophes"] },
      { number: 11, title: "Stars and Planets",         pages: "145–158",topics: ["Science vocabulary", "Fact vs. opinion", "Present perfect tense"] },
      { number: 12, title: "Revision & Assessment",     pages: "159–196",topics: ["Comprehension practice", "Grammar review", "Creative writing task"] },
    ],
  },
  {
    id: "maths5",
    title: "New Countdown Maths 5",
    subject: "Maths",
    grade: "5",
    publisher: "Oxford University Press",
    edition: "3rd Edition",
    totalPages: 212,
    chapters: [
      { number: 1,  title: "Whole Numbers",       pages: "1–22",   topics: ["Place value up to millions", "Comparing & ordering", "Rounding numbers"] },
      { number: 2,  title: "Fractions",            pages: "23–48",  topics: ["Equivalent fractions", "Addition & subtraction", "Mixed numbers"] },
      { number: 3,  title: "Decimals",             pages: "49–70",  topics: ["Decimal place value", "Multiplication of decimals", "Division of decimals"] },
      { number: 4,  title: "Percentages",          pages: "71–84",  topics: ["Percent of a quantity", "Converting fractions to %", "Real-world problems"] },
      { number: 5,  title: "Measurement",          pages: "85–102", topics: ["Units of length", "Units of mass", "Units of capacity"] },
      { number: 6,  title: "Geometry — Shapes",    pages: "103–122",topics: ["2D shape properties", "3D shape properties", "Angles"] },
      { number: 7,  title: "Area & Perimeter",     pages: "123–140",topics: ["Perimeter of polygons", "Area of rectangles", "Area of triangles"] },
      { number: 8,  title: "Data Handling",        pages: "141–158",topics: ["Tally charts", "Bar graphs", "Pie charts"] },
      { number: 9,  title: "Word Problems",        pages: "159–180",topics: ["Multi-step problems", "Problem-solving strategies", "Mixed operations"] },
      { number: 10, title: "Revision & Assessment",pages: "181–212",topics: ["Topic reviews", "Practice tests", "Mental maths"] },
    ],
  },
];

// ── Books Tab ─────────────────────────────────────────────────────────────────

function BooksTab({ onGoToSlos }: { onGoToSlos: () => void }) {
  const [expandedBook, setExpandedBook] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {BOOKS.map((book) => {
        const isExpanded = expandedBook === book.id;
        return (
          <div key={book.id} className="border border-dars-rule-light rounded-xl overflow-hidden">
            {/* Book card header */}
            <button
              type="button"
              onClick={() => setExpandedBook(isExpanded ? null : book.id)}
              className="w-full text-left bg-white hover:bg-dars-parchment transition-colors cursor-pointer border-none"
            >
              <div className="flex items-stretch">
                {/* Spine colour strip */}
                <div className={`w-2 shrink-0 ${book.subject === "English" ? "bg-blue-400" : "bg-amber-400"}`} />
                <div className="flex-1 px-5 py-4 flex items-center gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-0.5">
                      <span className="text-base font-serif font-semibold text-dars-ink">{book.title}</span>
                      <span className="text-[10px] font-semibold tracking-wide uppercase bg-dars-parchment-deep text-dars-muted px-1.5 py-0.5 rounded">
                        Grade {book.grade}
                      </span>
                      <span className={`text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded ${book.subject === "English" ? "bg-blue-100 text-blue-800" : "bg-amber-100 text-amber-800"}`}>
                        {book.subject}
                      </span>
                    </div>
                    <p className="text-xs text-dars-muted">{book.publisher} · {book.edition} · {book.totalPages} pages · {book.chapters.length} chapters</p>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <a
                      href="#"
                      onClick={(e) => e.stopPropagation()}
                      className="flex items-center gap-1.5 text-xs font-semibold text-dars-terra border border-dars-terra px-3 py-1.5 rounded-md hover:bg-dars-terra hover:text-white transition-colors no-underline"
                    >
                      <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                      View PDF
                    </a>
                    <svg
                      className={`h-4 w-4 text-dars-muted transition-transform ${isExpanded ? "rotate-180" : ""}`}
                      viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
                    >
                      <polyline points="6 9 12 15 18 9" />
                    </svg>
                  </div>
                </div>
              </div>
            </button>

            {/* Table of contents */}
            {isExpanded && (
              <div className="border-t border-dars-rule-light bg-dars-parchment px-6 py-5">
                <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest mb-3">Table of Contents</p>
                <div className="space-y-px">
                  {book.chapters.map((ch) => (
                    <div key={ch.number} className="flex items-start gap-3 py-2.5 border-b border-dars-rule-light last:border-0">
                      <span className="text-xs font-bold text-dars-muted w-6 shrink-0 pt-0.5">{ch.number}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline justify-between gap-4">
                          <span className="text-sm font-medium text-dars-ink">{ch.title}</span>
                          <span className="text-xs text-dars-muted shrink-0">pp. {ch.pages}</span>
                        </div>
                        <ul className="mt-1 space-y-0.5">
                          {ch.topics.map((t) => {
                            const linkedSubs = TOPIC_TO_SUBSLOS[t] ?? [];
                            return (
                              <li key={t} className="text-xs text-dars-muted flex items-start gap-1.5">
                                <span className="h-1 w-1 rounded-full bg-dars-muted/40 shrink-0 mt-1.5" />
                                <span>
                                  {t}
                                  {linkedSubs.length > 0 && (
                                    <span className="ml-1.5 inline-flex items-center gap-1 flex-wrap">
                                      <span className="text-[10px] text-dars-muted">→</span>
                                      {linkedSubs.map((code) => (
                                        <button
                                          key={code}
                                          type="button"
                                          onClick={(e) => { e.stopPropagation(); onGoToSlos(); }}
                                          className="text-[10px] font-semibold text-dars-terra underline decoration-dotted hover:decoration-solid cursor-pointer bg-transparent border-none p-0"
                                        >
                                          {code}
                                        </button>
                                      ))}
                                    </span>
                                  )}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ── Static Class Data ─────────────────────────────────────────────────────────

interface SchoolClass {
  id: string;
  grade: string;
  section: string;
  subject: Subject;
  students: number;
  bookId: string;
  chaptersCompleted: number;
  totalChapters: number;
  slosCovered: number;
  totalSlos: number;
}

const CLASSES: SchoolClass[] = [
  { id: "4a-eng", grade: "4", section: "A", subject: "English", students: 32, bookId: "eng5", chaptersCompleted: 5, totalChapters: 12, slosCovered: 6,  totalSlos: 12 },
  { id: "4b-eng", grade: "4", section: "B", subject: "English", students: 28, bookId: "eng5", chaptersCompleted: 4, totalChapters: 12, slosCovered: 4,  totalSlos: 12 },
  { id: "4a-maths", grade: "4", section: "A", subject: "Maths",   students: 32, bookId: "maths5", chaptersCompleted: 3, totalChapters: 10, slosCovered: 5,  totalSlos: 10 },
  { id: "5a-eng", grade: "5", section: "A", subject: "English", students: 30, bookId: "eng5", chaptersCompleted: 7, totalChapters: 12, slosCovered: 9,  totalSlos: 12 },
  { id: "5b-eng", grade: "5", section: "B", subject: "English", students: 27, bookId: "eng5", chaptersCompleted: 6, totalChapters: 12, slosCovered: 7,  totalSlos: 12 },
  { id: "5a-maths", grade: "5", section: "A", subject: "Maths",   students: 30, bookId: "maths5", chaptersCompleted: 6, totalChapters: 10, slosCovered: 7,  totalSlos: 10 },
];

// ── Classes Tab ───────────────────────────────────────────────────────────────

function ClassesTab() {
  const [activeClass, setActiveClass] = useState<string | null>(null);
  const [expandedBook, setExpandedBook] = useState<string | null>(null);

  const cls = CLASSES.find((c) => c.id === activeClass) ?? null;
  const book = cls ? BOOKS.find((b) => b.id === cls.bookId) ?? null : null;

  if (cls && book) {
    return (
      <div>
        {/* Breadcrumb */}
        <button
          type="button"
          onClick={() => { setActiveClass(null); setExpandedBook(null); }}
          className="flex items-center gap-1.5 text-sm text-dars-terra font-medium mb-5 cursor-pointer bg-transparent border-none hover:opacity-80"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="15 18 9 12 15 6"/></svg>
          All Classes
        </button>

        {/* Class header */}
        <div className="flex items-center gap-4 mb-6">
          <div>
            <h2 className="text-xl font-serif font-bold text-dars-ink">
              Grade {cls.grade}-{cls.section} &nbsp;·&nbsp; {cls.subject}
            </h2>
            <p className="text-xs text-dars-muted mt-0.5">{cls.students} students &nbsp;·&nbsp; Academic Year 2026–2027</p>
          </div>
          <div className="ml-auto flex gap-3">
            <div className="text-center px-4 py-2 bg-dars-parchment border border-dars-rule-light rounded-lg">
              <p className="text-lg font-serif font-bold text-dars-ink">{cls.chaptersCompleted}<span className="text-xs font-normal text-dars-muted">/{cls.totalChapters}</span></p>
              <p className="text-[10px] text-dars-muted">Chapters done</p>
            </div>
            <div className="text-center px-4 py-2 bg-dars-parchment border border-dars-rule-light rounded-lg">
              <p className="text-lg font-serif font-bold text-dars-ink">{cls.slosCovered}<span className="text-xs font-normal text-dars-muted">/{cls.totalSlos}</span></p>
              <p className="text-[10px] text-dars-muted">SLOs covered</p>
            </div>
          </div>
        </div>

        {/* Book card */}
        <div className="border border-dars-rule-light rounded-xl overflow-hidden">
          <button
            type="button"
            onClick={() => setExpandedBook(expandedBook === book.id ? null : book.id)}
            className="w-full text-left bg-white hover:bg-dars-parchment transition-colors cursor-pointer border-none"
          >
            <div className="flex items-stretch">
              <div className={`w-2 shrink-0 ${book.subject === "English" ? "bg-blue-400" : "bg-amber-400"}`} />
              <div className="flex-1 px-5 py-4 flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <span className="text-base font-serif font-semibold text-dars-ink">{book.title}</span>
                    <span className="text-[10px] font-semibold tracking-wide uppercase bg-dars-parchment-deep text-dars-muted px-1.5 py-0.5 rounded">Grade {book.grade}</span>
                  </div>
                  <p className="text-xs text-dars-muted">{book.publisher} · {book.edition} · {book.totalPages} pages · {book.chapters.length} chapters</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <a href="#" onClick={(e) => e.stopPropagation()} className="flex items-center gap-1.5 text-xs font-semibold text-dars-terra border border-dars-terra px-3 py-1.5 rounded-md hover:bg-dars-terra hover:text-white transition-colors no-underline">
                    <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
                    View PDF
                  </a>
                  <svg className={`h-4 w-4 text-dars-muted transition-transform ${expandedBook === book.id ? "rotate-180" : ""}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
                </div>
              </div>
            </div>
          </button>

          {expandedBook === book.id && (
            <div className="border-t border-dars-rule-light bg-dars-parchment px-6 py-5">
              <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest mb-3">Table of Contents</p>
              <div className="space-y-px">
                {book.chapters.map((ch) => {
                  const done = ch.number <= cls.chaptersCompleted;
                  return (
                    <div key={ch.number} className={`flex items-start gap-3 py-2.5 border-b border-dars-rule-light last:border-0 ${done ? "" : "opacity-50"}`}>
                      <span className="text-xs font-bold text-dars-muted w-6 shrink-0 pt-0.5">{ch.number}</span>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-baseline justify-between gap-4">
                          <span className="text-sm font-medium text-dars-ink">{ch.title}</span>
                          <div className="flex items-center gap-2 shrink-0">
                            <span className="text-xs text-dars-muted">pp. {ch.pages}</span>
                            {done && <span className="text-[10px] font-semibold tracking-wide uppercase bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded">Done</span>}
                          </div>
                        </div>
                        <ul className="mt-1 space-y-0.5">
                          {ch.topics.map((t) => {
                            const linkedSubs = TOPIC_TO_SUBSLOS[t] ?? [];
                            return (
                              <li key={t} className="text-xs text-dars-muted flex items-start gap-1.5">
                                <span className="h-1 w-1 rounded-full bg-dars-muted/40 shrink-0 mt-1.5" />
                                <span>{t}{linkedSubs.length > 0 && <span className="ml-1.5 text-[10px] text-dars-terra font-medium">→ {linkedSubs.join(", ")}</span>}</span>
                              </li>
                            );
                          })}
                        </ul>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Class grid
  const grades = [...new Set(CLASSES.map((c) => c.grade))].sort();

  return (
    <div>
      {grades.map((grade) => (
        <div key={grade} className="mb-6">
          <p className="text-[10px] font-semibold text-dars-muted uppercase tracking-widest mb-3">Grade {grade}</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {CLASSES.filter((c) => c.grade === grade).map((c) => {
              const chapterPct = Math.round((c.chaptersCompleted / c.totalChapters) * 100);
              const sloPct = Math.round((c.slosCovered / c.totalSlos) * 100);
              return (
                <button
                  key={c.id}
                  type="button"
                  onClick={() => setActiveClass(c.id)}
                  className="text-left bg-white border border-dars-rule-light rounded-xl p-4 hover:border-dars-terra hover:shadow-sm transition-all cursor-pointer"
                >
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="text-base font-serif font-semibold text-dars-ink">Grade {c.grade}-{c.section}</p>
                      <p className="text-xs text-dars-muted">{c.subject} &nbsp;·&nbsp; {c.students} students</p>
                    </div>
                    <span className={`text-[10px] font-semibold tracking-wide uppercase px-1.5 py-0.5 rounded ${c.subject === "English" ? "bg-blue-100 text-blue-800" : "bg-amber-100 text-amber-800"}`}>
                      {c.subject}
                    </span>
                  </div>
                  <div className="space-y-2">
                    <div>
                      <div className="flex justify-between text-[10px] text-dars-muted mb-1">
                        <span>Chapters</span>
                        <span>{c.chaptersCompleted}/{c.totalChapters}</span>
                      </div>
                      <div className="h-1.5 bg-dars-rule-light rounded-full overflow-hidden">
                        <div className="h-full bg-dars-terra rounded-full" style={{ width: `${chapterPct}%` }} />
                      </div>
                    </div>
                    <div>
                      <div className="flex justify-between text-[10px] text-dars-muted mb-1">
                        <span>SLOs covered</span>
                        <span>{c.slosCovered}/{c.totalSlos}</span>
                      </div>
                      <div className="h-1.5 bg-dars-rule-light rounded-full overflow-hidden">
                        <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${sloPct}%` }} />
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "classes" | "books" | "syllabus" | "lessons" | "slos";

export default function CurriculumPage() {
  const [tab, setTab] = useState<Tab>("classes");

  return (
    <div className="p-8 max-w-5xl">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-serif font-bold text-dars-ink">Curriculum Planner</h1>
        <p className="text-sm text-dars-muted mt-1">Academic Year 2026–2027</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 border-b border-dars-rule-light pb-3">
        <TabButton label="Classes" active={tab === "classes"} onClick={() => setTab("classes")} />
        <TabButton label="Books" active={tab === "books"} onClick={() => setTab("books")} />
        <TabButton label="Syllabus" active={tab === "syllabus"} onClick={() => setTab("syllabus")} />
        <TabButton label="Lesson Breakdown" active={tab === "lessons"} onClick={() => setTab("lessons")} />
        <TabButton label="SLO Tracker" active={tab === "slos"} onClick={() => setTab("slos")} />
      </div>

      {/* Tab content */}
      {tab === "classes" && <ClassesTab />}
      {tab === "books" && <BooksTab onGoToSlos={() => setTab("slos")} />}
      {tab === "syllabus" && <SyllabusTab />}
      {tab === "lessons" && <LessonsTab />}
      {tab === "slos" && <SloTab />}
    </div>
  );
}
