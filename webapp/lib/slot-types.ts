/**
 * Mirror of `server/src/dars/v2_api/lp_types.py` for use in the breakdown
 * editor. Duplicated as a small static table rather than fetched, per
 * D-3 in `docs/features/breakdown-slot-editing/01-decision-log.md`. The
 * server still validates on every PATCH so this only drives the UI's
 * legal-combo dropdown.
 *
 * Keep in sync with the server-side constant if it changes.
 */

import type { BreakdownSlot } from "./dars-api";

export type SlotType = BreakdownSlot["slot_type"];

export const VALID_SLOT_TYPES: readonly SlotType[] = [
  "lesson",
  "formative_assessment",
  "summative_assessment",
  "revision",
];

export const LP_TYPES_BY_SUBJECT: Record<string, readonly string[]> = {
  Eng: [
    "reading",
    "comprehension_word_meanings",
    "comprehension_qa",
    "grammar",
    "creative_writing",
    "revision",
  ],
  Urdu: [
    "reading",
    "comprehension_word_meanings",
    "comprehension_qa",
    "grammar",
    "creative_writing",
    "revision",
  ],
  Maths: ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
  Science: ["revision"],
  GK: ["revision"],
};

const LP_TYPE_LABELS: Record<string, string> = {
  reading: "Reading",
  comprehension_word_meanings: "Comprehension — word meanings",
  comprehension_qa: "Comprehension — Q&A",
  grammar: "Grammar",
  creative_writing: "Creative writing",
  concrete: "Concrete",
  pictorial_and_abstract: "Pictorial & abstract",
  word_problems: "Word problems",
  revision: "Revision",
};

export interface SlotCombo {
  value: string;
  label: string;
  slot_type: SlotType;
  lp_type: string | null;
}

/**
 * Build the flat list of legal (slot_type, lp_type) combos for a subject.
 * Lessons enumerate each non-revision lp_type. Revision is a standalone
 * row (`slot_type=revision`, `lp_type=revision`). Both assessment types
 * are present with `lp_type=null`. The `value` field is `<slot_type>::<lp_type|none>`
 * which the editor parses back on save.
 */
export function buildSlotCombos(subjectCode: string): SlotCombo[] {
  const lpTypes = LP_TYPES_BY_SUBJECT[subjectCode] ?? [];
  const combos: SlotCombo[] = [];

  for (const lp of lpTypes) {
    if (lp === "revision") continue;
    combos.push({
      value: `lesson::${lp}`,
      label: `Lesson — ${LP_TYPE_LABELS[lp] ?? lp}`,
      slot_type: "lesson",
      lp_type: lp,
    });
  }

  combos.push({
    value: "formative_assessment::none",
    label: "Formative assessment",
    slot_type: "formative_assessment",
    lp_type: null,
  });
  combos.push({
    value: "summative_assessment::none",
    label: "Summative assessment",
    slot_type: "summative_assessment",
    lp_type: null,
  });

  if (lpTypes.includes("revision")) {
    combos.push({
      value: "revision::revision",
      label: "Revision",
      slot_type: "revision",
      lp_type: "revision",
    });
  }

  return combos;
}

export function comboValueFromSlot(slot: {
  slot_type: SlotType;
  lp_type: string | null;
}): string {
  return `${slot.slot_type}::${slot.lp_type ?? "none"}`;
}

export function parseComboValue(value: string): {
  slot_type: SlotType;
  lp_type: string | null;
} {
  const [st, lp] = value.split("::");
  return {
    slot_type: st as SlotType,
    lp_type: lp === "none" ? null : lp,
  };
}

/**
 * Default combo for a new slot in this subject. Used by F1.3's
 * "+ Add slot" button. Per the phase doc: lesson + first non-revision
 * lp_type for normal subjects; revision for Science/GK which have no
 * lesson lp_types.
 */
export function defaultComboForNewSlot(subjectCode: string): SlotCombo {
  const combos = buildSlotCombos(subjectCode);
  const firstLesson = combos.find((c) => c.slot_type === "lesson");
  if (firstLesson) return firstLesson;
  const rev = combos.find((c) => c.slot_type === "revision");
  if (rev) return rev;
  // Falls back to formative_assessment so we don't crash if subject is
  // unknown; server will 422 on save, surfacing the issue.
  return combos[0];
}
