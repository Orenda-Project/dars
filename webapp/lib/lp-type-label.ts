/**
 * lp-context-header F-2.1 / D-3 — the single place a raw `lp_type` enum value
 * is turned into a human-readable label for display.
 *
 * The backend sends raw enum values (the API contract). Labels are purely a
 * presentation concern, so this map lives on the frontend and is the only
 * translator: never render `lp_type` raw in the UI again.
 *
 * Values per subject are defined in
 * server/src/dars/breakdown/planner_models.py `VALID_LP_TYPES`.
 */

const LP_TYPE_LABELS: Record<string, string> = {
  reading: "Reading",
  comprehension_word_meanings: "Comprehension: Word Meanings",
  comprehension_qa: "Comprehension: Q&A",
  grammar: "Grammar",
  creative_writing: "Creative Writing",
  revision: "Revision",
  concrete: "Concrete",
  pictorial_and_abstract: "Pictorial & Abstract",
  word_problems: "Word Problems",
};

/** The full known label map (e.g. for building a legend/filter). */
export const lpTypeLabels = LP_TYPE_LABELS;

/**
 * Human-readable label for a raw `lp_type`.
 *
 * - `null` / empty → `null` (caller hides the badge).
 * - known value → its mapped label.
 * - unknown non-empty value → a title-cased, underscore-split fallback, so a
 *   new backend enum never renders blank or as a raw snake_case string.
 */
export function lpTypeLabel(lpType: string | null | undefined): string | null {
  if (!lpType) return null;
  const known = LP_TYPE_LABELS[lpType];
  if (known) return known;
  return lpType
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
