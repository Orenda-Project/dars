/**
 * Mirror of server-side `iter_questions` from
 * dars/generated_exams/tagging_service.py.
 *
 * Walks the exam_json tree in deterministic order and yields a flat
 * (composite_key, index, text, marks) sequence. The mastery form uses
 * this `index` as `question_index` in submissions; the server uses the
 * same walk to map index → composite_key → sub_slo_id.
 *
 * If the server's walk changes, this MUST be kept in sync.
 */

export interface ExamQuestionWalkItem {
  /** "{scope}:{category}:{type}:{index_within_type}" */
  key: string;
  /** Flat 0..N-1 index used as question_index in submissions. */
  index: number;
  text: string;
  marks: number | null;
}

const SCOPES = ["unseen", "seen"] as const;
const CATEGORIES = ["objective", "subjective"] as const;

export function walkExamQuestions(exam: unknown): ExamQuestionWalkItem[] {
  if (!isPlainObject(exam)) return [];
  const out: ExamQuestionWalkItem[] = [];
  let flat = 0;

  for (const scope of SCOPES) {
    const scopeBlock = (exam as Record<string, unknown>)[scope];
    if (!isPlainObject(scopeBlock)) continue;
    for (const category of CATEGORIES) {
      const catBlock = (scopeBlock as Record<string, unknown>)[category];
      if (!isPlainObject(catBlock)) continue;
      for (const [qtype, items] of Object.entries(catBlock)) {
        if (!Array.isArray(items)) continue;
        items.forEach((q, i) => {
          if (!isPlainObject(q)) return;
          const text = pickText(q);
          if (!text) return;
          const marks = typeof q.marks === "number" ? q.marks : null;
          out.push({
            key: `${scope}:${category}:${qtype}:${i}`,
            index: flat,
            text,
            marks,
          });
          flat += 1;
        });
      }
    }
  }
  return out;
}

function pickText(q: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const field of ["main_question", "question", "passage"]) {
    const v = q[field];
    if (typeof v === "string" && v.trim()) parts.push(v.trim());
  }
  return parts.join("\n");
}

function isPlainObject(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}
