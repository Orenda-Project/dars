/**
 * Client-side, advisory planner warnings (planner-ux-upgrade, F1.3 / D-4).
 *
 * Mirrors the overlap + zero-teaching-days logic of the server's authoritative
 * `compute_range_warnings` in `server/src/dars/breakdown/chapter_calendar.py`.
 * The server stays the source of truth (D-4): these warnings only INFORM the
 * teacher in the Syllabus-tab planner and never block a save. A future
 * server-authoritative warning endpoint can replace this mirror without
 * changing the UI contract.
 *
 * Parity notes vs the Python fn:
 *   - Both consider only chapters with BOTH a start_date AND end_date set, and
 *     sort by (start_date, position). ISO `YYYY-MM-DD` strings sort and compare
 *     lexicographically the same as real dates, so string compare matches the
 *     server's `date` compare exactly.
 *   - overlap: for each position-consecutive pair in the sorted dated list,
 *     emit when `cur.start_date <= prev.end_date` — identical predicate.
 *   - zero_teaching_days: the server recomputes teaching days; we instead read
 *     the payload's holiday-aware `slot_count` (server-computed per read) and
 *     treat `slot_count === 0` on a dated chapter as zero teaching days. This is
 *     the same condition, just sourced from the precomputed count rather than
 *     re-walking the calendar client-side.
 *   - We do NOT emit `gap` (out of scope for v1). Holiday-in-range is a visual
 *     hint (F1.2), NOT a warning row here.
 */

export type PlannerWarning =
  | { type: "overlap"; chapterIds: string[] }
  | { type: "zero_teaching_days"; chapterIds: string[] };

interface WarningChapter {
  book_chapter_id: string;
  position: number;
  start_date: string | null;
  end_date: string | null;
  slot_count: number;
}

export function computePlannerWarnings(
  chapters: WarningChapter[],
): PlannerWarning[] {
  const warnings: PlannerWarning[] = [];

  // Only dated chapters participate; sort by (start_date, position) to match
  // the server. Both keys are ascending; ISO date strings compare correctly.
  const dated = chapters
    .filter((c) => c.start_date && c.end_date)
    .sort((a, b) => {
      if (a.start_date! < b.start_date!) return -1;
      if (a.start_date! > b.start_date!) return 1;
      return a.position - b.position;
    });

  // zero_teaching_days: a dated range with no teaching periods. The payload's
  // slot_count is the holiday-aware teaching-period capacity (server-computed),
  // so slot_count === 0 on a dated row is exactly the server's condition.
  for (const c of dated) {
    if (c.slot_count === 0) {
      warnings.push({ type: "zero_teaching_days", chapterIds: [c.book_chapter_id] });
    }
  }

  // overlap: position-consecutive dated pairs whose ranges intersect.
  for (let i = 1; i < dated.length; i++) {
    const prev = dated[i - 1];
    const cur = dated[i];
    if (cur.start_date! <= prev.end_date!) {
      warnings.push({
        type: "overlap",
        chapterIds: [prev.book_chapter_id, cur.book_chapter_id],
      });
    }
  }

  return warnings;
}
