// Frontend-only mock data for the Teacher Sample App.
//
// Why: The teacher-app is a demo integration. To showcase the experience without
// depending on backend LP/exam generation (which is slow and non-deterministic),
// every "View LP" and "View Exam" inside /teacher-app/** is short-circuited to
// return one of these polished samples, picked by subject.

import type { GeneratedLPResponse, GeneratedExamResponse } from "./school-api";

type SubjectKey = "math" | "english" | "urdu";

function normalizeSubject(raw: string | null | undefined): SubjectKey {
  const s = (raw ?? "").trim().toLowerCase();
  if (s.includes("math")) return "math";
  if (s.includes("urdu") || s.includes("اردو")) return "urdu";
  return "english";
}

// ---------------------------------------------------------------------------
// Lesson plan HTML — matches the Georgia/serif style used in curriculum-demo
// ---------------------------------------------------------------------------

const LP_STYLE_OPEN =
  '<div style="font-family: Georgia, serif; line-height: 1.7; color: #1c1410;">';
const LP_STYLE_CLOSE = "</div>";

const SECTION_HEADER =
  'style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #7a6b62; margin: 1.25rem 0 0.5rem;"';

function lpHtml(opts: {
  title: string;
  subtitle: string;
  objectives: string[];
  warmup: string;
  mainSteps: { label: string; body: string }[];
  wrapUp: string;
  slos: string;
  materials: string;
}) {
  const obj = opts.objectives.map((o) => `<li>${o}</li>`).join("");
  const steps = opts.mainSteps
    .map(
      (s) =>
        `<p style="margin: 0 0 0.75rem;"><strong>${s.label}:</strong> ${s.body}</p>`
    )
    .join("");

  return `${LP_STYLE_OPEN}
  <h2 style="font-size: 1.15rem; font-weight: 700; margin: 0 0 0.25rem;">${opts.title}</h2>
  <p style="font-size: 0.78rem; color: #7a6b62; margin: 0 0 1.25rem;">${opts.subtitle}</p>

  <h3 ${SECTION_HEADER}>Learning Objectives</h3>
  <ul style="margin: 0 0 1rem 1.2rem; font-size: 0.92rem;">${obj}</ul>

  <h3 ${SECTION_HEADER}>Materials</h3>
  <p style="font-size: 0.92rem; margin: 0 0 0.5rem;">${opts.materials}</p>

  <h3 ${SECTION_HEADER}>Warm-Up (5 min)</h3>
  <p style="font-size: 0.92rem; margin: 0 0 0.5rem;">${opts.warmup}</p>

  <h3 ${SECTION_HEADER}>Main Activity (25 min)</h3>
  <div style="font-size: 0.92rem;">${steps}</div>

  <h3 ${SECTION_HEADER}>Wrap-Up (5 min)</h3>
  <p style="font-size: 0.92rem; margin: 0 0 0.5rem;">${opts.wrapUp}</p>

  <h3 ${SECTION_HEADER}>SLOs Addressed</h3>
  <p style="font-size: 0.85rem; color: #7a6b62; margin: 0;">${opts.slos}</p>
${LP_STYLE_CLOSE}`;
}

const LP_CONTENT: Record<SubjectKey, string> = {
  math: lpHtml({
    title: "Fractions: Adding Like Denominators",
    subtitle: "Mathematics · Grade 5 · Concept Lesson",
    objectives: [
      "Students will identify fractions with the same denominator.",
      "Students will add two fractions with like denominators correctly.",
      "Students will represent the sum visually using bar models.",
    ],
    materials:
      "Whiteboard, fraction strips (paper), student notebooks, textbook page 42.",
    warmup:
      "Draw a pizza on the board cut into 8 equal slices. Shade 3 slices and ask: <em>“What fraction is shaded?”</em> Then shade 2 more and ask: <em>“Now what fraction is shaded?”</em> Use this to lead into addition.",
    mainSteps: [
      {
        label: "Step 1 — Model on the board (8 min)",
        body:
          "Write 2/8 + 3/8 on the board. Draw two bar models stacked. Show that the denominator stays the same and only the numerators add.",
      },
      {
        label: "Step 2 — Guided practice (10 min)",
        body:
          "Work through three examples together: 1/5 + 2/5, 4/9 + 3/9, 2/6 + 3/6. Have students come to the board.",
      },
      {
        label: "Step 3 — Independent practice (7 min)",
        body:
          "Students complete Q1–Q6 on page 42. Walk around and check work. Pair stronger students with those needing help.",
      },
    ],
    wrapUp:
      "Ask three students to share one example each. Common error to highlight: adding the denominators. Remind them only numerators add when denominators are the same.",
    slos: "M5.NF.1 · M5.NF.2 · M5.NF.3",
  }),

  english: lpHtml({
    title: "Reading: The Clever Crow",
    subtitle: "English · Grade 4 · Reading Comprehension",
    objectives: [
      "Students will read the passage aloud with correct pronunciation and pacing.",
      "Students will identify new vocabulary words and infer meaning from context.",
      "Students will answer literal and inferential comprehension questions.",
    ],
    materials:
      "Textbook, whiteboard, student notebooks, vocabulary flashcards (optional).",
    warmup:
      "Show the picture on page 18. Ask: <em>“What is the crow doing? What do you think will happen next?”</em> Take 2–3 predictions.",
    mainSteps: [
      {
        label: "Step 1 — Teacher reads aloud (8 min)",
        body:
          "Read the passage with expression. Stop at each new vocabulary word (<em>thirsty, pebble, gradually</em>) and have students underline it.",
      },
      {
        label: "Step 2 — Vocabulary in context (10 min)",
        body:
          "Write the underlined words on the board. For each, ask students to infer the meaning from the sentence. Confirm and have them note the meaning in their copies.",
      },
      {
        label: "Step 3 — Comprehension questions (7 min)",
        body:
          "Students answer Q1–Q4 from the textbook orally as a class. Q5 (inferential — “Why was the crow clever?”) for written work.",
      },
    ],
    wrapUp:
      "Ask: <em>“What lesson does this story teach us?”</em> Encourage answers about patience and problem-solving. Assign Q5 as homework.",
    slos: "R4.1 · R4.2 · V4.1 · C4.3",
  }),

  urdu: lpHtml({
    title: "نظم: ہمارا وطن",
    subtitle: "اردو · جماعت پنجم · نظم خوانی",
    objectives: [
      "طلبہ نظم کو درست تلفظ اور روانی کے ساتھ پڑھ سکیں گے۔",
      "طلبہ نظم کے مرکزی خیال کی شناخت کر سکیں گے۔",
      "طلبہ نظم میں استعمال شدہ مشکل الفاظ کے معنی سمجھ سکیں گے۔",
    ],
    materials: "اردو کی کتاب، تختہ سیاہ، طلبہ کی کاپیاں۔",
    warmup:
      "تختے پر لفظ <em>“وطن”</em> لکھیں اور طلبہ سے پوچھیں: <em>“وطن سے آپ کیا سمجھتے ہیں؟”</em> دو تین جوابات لیں اور تختے پر لکھیں۔",
    mainSteps: [
      {
        label: "مرحلہ ۱ — استاد کا پڑھنا (8 منٹ)",
        body:
          "نظم کو واضح آواز اور درست لہجے میں پڑھیں۔ طلبہ خاموشی سے کتاب میں ساتھ دیکھتے رہیں۔",
      },
      {
        label: "مرحلہ ۲ — مشترکہ پڑھائی (10 منٹ)",
        body:
          "نظم کو بند بہ بند پڑھیں۔ ہر بند کے بعد طلبہ سے مرکزی خیال پوچھیں۔ مشکل الفاظ (<em>سرزمین، آبرو، فخر</em>) کے معنی تختے پر لکھیں۔",
      },
      {
        label: "مرحلہ ۳ — انفرادی مشق (7 منٹ)",
        body:
          "طلبہ صفحہ ۲۴ کے سوالات ۱ تا ۳ اپنی کاپیوں میں لکھیں۔ استاد گھوم پھر کر مدد کریں۔",
      },
    ],
    wrapUp:
      "دو طلبہ کو بلا کر نظم کا پہلا بند سنوائیں۔ گھر کا کام: نظم کے کوئی دو بند یاد کرنا۔",
    slos: "U5.R1 · U5.R2 · U5.V1",
  }),
};

// ---------------------------------------------------------------------------
// Exam JSON — shape consumed by the structured renderer in the slide-over
// ---------------------------------------------------------------------------

export interface MockExamQuestion {
  id: string;
  type: "MCQ" | "SHORT" | "LONG";
  text: string;
  options?: string[];
  marks: number;
}

export interface MockExamPaper {
  title: string;
  subject: string;
  grade: string;
  metadata: {
    total_marks: number;
    duration_minutes: number;
    question_count: number;
  };
  sections: { title: string; questions: MockExamQuestion[] }[];
}

const EXAM_CONTENT: Record<SubjectKey, MockExamPaper> = {
  math: {
    title: "Half-Yearly Assessment",
    subject: "Mathematics",
    grade: "5",
    metadata: { total_marks: 30, duration_minutes: 60, question_count: 10 },
    sections: [
      {
        title: "Section A — Multiple Choice (1 mark each)",
        questions: [
          {
            id: "q1",
            type: "MCQ",
            text: "What is 3/8 + 2/8?",
            options: ["5/16", "5/8", "6/8", "1/2"],
            marks: 1,
          },
          {
            id: "q2",
            type: "MCQ",
            text: "Which of the following is an improper fraction?",
            options: ["3/5", "7/4", "2/9", "1/2"],
            marks: 1,
          },
          {
            id: "q3",
            type: "MCQ",
            text: "Round 4.678 to the nearest tenth.",
            options: ["4.6", "4.7", "4.68", "4.8"],
            marks: 1,
          },
          {
            id: "q4",
            type: "MCQ",
            text: "The perimeter of a square with side 6 cm is:",
            options: ["12 cm", "24 cm", "36 cm", "18 cm"],
            marks: 1,
          },
        ],
      },
      {
        title: "Section B — Short Answer (2 marks each)",
        questions: [
          {
            id: "q5",
            type: "SHORT",
            text: "Add: 5/12 + 4/12. Show your working.",
            marks: 2,
          },
          {
            id: "q6",
            type: "SHORT",
            text: "Convert 7/2 to a mixed number.",
            marks: 2,
          },
          {
            id: "q7",
            type: "SHORT",
            text: "Find the area of a rectangle 8 cm long and 5 cm wide.",
            marks: 2,
          },
          {
            id: "q8",
            type: "SHORT",
            text: "Write 0.45 as a fraction in its simplest form.",
            marks: 2,
          },
        ],
      },
      {
        title: "Section C — Long Answer (7 marks each)",
        questions: [
          {
            id: "q9",
            type: "LONG",
            text:
              "A shopkeeper had 24 1/2 kg of sugar. He sold 9 3/4 kg in the morning and 7 1/2 kg in the evening. How much sugar is left? Show all steps.",
            marks: 7,
          },
          {
            id: "q10",
            type: "LONG",
            text:
              "A rectangular field is 45 m long and 28 m wide. (a) Find its perimeter. (b) Find its area. (c) If fencing costs Rs. 120 per metre, what is the total cost?",
            marks: 7,
          },
        ],
      },
    ],
  },

  english: {
    title: "Half-Yearly Assessment",
    subject: "English",
    grade: "4",
    metadata: { total_marks: 30, duration_minutes: 60, question_count: 10 },
    sections: [
      {
        title: "Section A — Multiple Choice (1 mark each)",
        questions: [
          {
            id: "q1",
            type: "MCQ",
            text: "Choose the correct synonym of 'happy'.",
            options: ["Sad", "Joyful", "Angry", "Tired"],
            marks: 1,
          },
          {
            id: "q2",
            type: "MCQ",
            text: "Which of the following is a noun?",
            options: ["Quickly", "Beautiful", "Lahore", "Run"],
            marks: 1,
          },
          {
            id: "q3",
            type: "MCQ",
            text: "Pick the correctly punctuated sentence.",
            options: [
              "where is my book",
              "Where is my book?",
              "where is my book.",
              "Where is my book",
            ],
            marks: 1,
          },
          {
            id: "q4",
            type: "MCQ",
            text: "The opposite of 'brave' is:",
            options: ["Strong", "Cowardly", "Kind", "Tall"],
            marks: 1,
          },
        ],
      },
      {
        title: "Section B — Short Answer (2 marks each)",
        questions: [
          {
            id: "q5",
            type: "SHORT",
            text: "Write the plural of: child, mouse, goose, tooth.",
            marks: 2,
          },
          {
            id: "q6",
            type: "SHORT",
            text:
              "Fill in the blanks with correct verb form: She ___ (go) to school every day.",
            marks: 2,
          },
          {
            id: "q7",
            type: "SHORT",
            text: "Use the word 'patience' in a meaningful sentence.",
            marks: 2,
          },
          {
            id: "q8",
            type: "SHORT",
            text:
              "Rewrite using correct punctuation: ali asked when will we go to islamabad",
            marks: 2,
          },
        ],
      },
      {
        title: "Section C — Long Answer (7 marks each)",
        questions: [
          {
            id: "q9",
            type: "LONG",
            text:
              "Write a paragraph of 8–10 sentences about 'My Best Friend'. Include their name, why they are special to you, and one memorable thing you did together.",
            marks: 7,
          },
          {
            id: "q10",
            type: "LONG",
            text:
              "Read the passage on the back of the paper and answer in your own words: (a) Who is the main character? (b) What problem did they face? (c) How did they solve it? (d) What lesson does the story teach?",
            marks: 7,
          },
        ],
      },
    ],
  },

  urdu: {
    title: "ششماہی امتحان",
    subject: "اردو",
    grade: "5",
    metadata: { total_marks: 30, duration_minutes: 60, question_count: 10 },
    sections: [
      {
        title: "حصہ الف — کثیر الانتخابی سوالات (1 نمبر فی سوال)",
        questions: [
          {
            id: "q1",
            type: "MCQ",
            text: "لفظ 'دانا' کا متضاد کیا ہے؟",
            options: ["عقلمند", "نادان", "ہوشیار", "سمجھدار"],
            marks: 1,
          },
          {
            id: "q2",
            type: "MCQ",
            text: "'کتاب' کی جمع ہے:",
            options: ["کتب", "کتابیں", "کتابوں", "الف اور ب دونوں"],
            marks: 1,
          },
          {
            id: "q3",
            type: "MCQ",
            text: "علامہ اقبال کا تعلق کس شہر سے تھا؟",
            options: ["کراچی", "لاہور", "سیالکوٹ", "اسلام آباد"],
            marks: 1,
          },
          {
            id: "q4",
            type: "MCQ",
            text: "لفظ 'سچائی' کی صفت ہے:",
            options: ["سچا", "جھوٹ", "بات", "اچھائی"],
            marks: 1,
          },
        ],
      },
      {
        title: "حصہ ب — مختصر جوابات (2 نمبر فی سوال)",
        questions: [
          {
            id: "q5",
            type: "SHORT",
            text: "کوئی تین مترادف الفاظ لکھیں: گھر، آسمان، استاد۔",
            marks: 2,
          },
          {
            id: "q6",
            type: "SHORT",
            text: "اپنا تعارف چار جملوں میں لکھیں۔",
            marks: 2,
          },
          {
            id: "q7",
            type: "SHORT",
            text: "لفظ 'محنت' کو جملے میں استعمال کریں۔",
            marks: 2,
          },
          {
            id: "q8",
            type: "SHORT",
            text: "درج ذیل کا واحد لکھیں: کتابیں، بچے، استانیاں، گلیاں۔",
            marks: 2,
          },
        ],
      },
      {
        title: "حصہ ج — تفصیلی جوابات (7 نمبر فی سوال)",
        questions: [
          {
            id: "q9",
            type: "LONG",
            text:
              "ایک مضمون لکھیں 'میرا پسندیدہ موسم' کم از کم آٹھ جملوں میں۔ موسم کا نام، اس کی خصوصیات اور آپ کو یہ کیوں پسند ہے، ضرور بیان کریں۔",
            marks: 7,
          },
          {
            id: "q10",
            type: "LONG",
            text:
              "نظم 'ہمارا وطن' کا مرکزی خیال اپنے الفاظ میں لکھیں اور بتائیں کہ ہمیں اپنے وطن سے محبت کیوں کرنی چاہیے۔",
            marks: 7,
          },
        ],
      },
    ],
  },
};

// ---------------------------------------------------------------------------
// Public API — drop-in replacements for getLessonPlan / getExam
// ---------------------------------------------------------------------------

function nowIso(): string {
  return new Date().toISOString();
}

export function getMockLP(
  lpId: string,
  subject: string | null | undefined
): GeneratedLPResponse {
  const key = normalizeSubject(subject);
  const subjectDisplay =
    key === "math" ? "Mathematics" : key === "urdu" ? "Urdu" : "English";
  return {
    id: lpId,
    client_id: "demo-client",
    external_id: null,
    status: "READY",
    grade: key === "english" ? "4" : "5",
    subject: subjectDisplay,
    curriculum: "PEF",
    topic: null,
    lp_type: null,
    content: LP_CONTENT[key],
    content_bilingual: null,
    error_message: null,
    created_at: nowIso(),
    updated_at: nowIso(),
  };
}

export function getMockExam(
  examId: string,
  subject: string | null | undefined
): GeneratedExamResponse {
  const key = normalizeSubject(subject);
  const paper = EXAM_CONTENT[key];
  return {
    id: examId,
    client_id: "demo-client",
    external_id: null,
    status: "READY",
    grade: paper.grade,
    subject: paper.subject,
    curriculum: "PEF",
    result: paper,
    error_message: null,
    created_at: nowIso(),
    updated_at: nowIso(),
  };
}

export function isMockExamPaper(value: unknown): value is MockExamPaper {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.title === "string" &&
    Array.isArray(v.sections) &&
    typeof v.metadata === "object"
  );
}

// ---------------------------------------------------------------------------
// Polling short-circuit — mocks are always READY, so callers can skip setInterval
// ---------------------------------------------------------------------------

export const TEACHER_APP_MOCKS_ENABLED = true;
