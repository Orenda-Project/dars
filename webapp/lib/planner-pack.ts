/**
 * Pure date-packing math for the planner (planner-ux-upgrade, Phase 2).
 *
 * This module is the ONLY home for the auto-pack / re-flow calendar arithmetic.
 * It is kept pure (no React, no fetch, no `dars-api`) so the date logic is
 * testable in isolation and the template stays prop-driven (webapp/CLAUDE.md
 * layering: templates do UI, the page owns hooks/fetch, date math lives here).
 *
 * What it computes (D-1): given a single anchor date the teacher chose, lay out
 * every yet-to-start chapter back-to-back so chapter N+1 starts on the next
 * teaching day after chapter N ends — no gaps, no overlaps by construction.
 *
 * Teaching-day model (mirrors the server's `chapter_slot_count` /
 * `compute_range_warnings` in `breakdown/chapter_calendar.py`): a TEACHING day
 * is Mon–Fri that is NOT an effective holiday for this CST. Weekends and
 * effective holidays are skipped — a chapter never *starts* on a non-teaching
 * day, and its span is measured in teaching days, not raw calendar days.
 *
 * Locks (D-6): locked chapters (status ≠ yet_to_start) are immutable — never
 * repacked, and excluded from the result. Packing flows the yet-to-start tail
 * forward from a cursor seeded the day after the last locked chapter.
 *
 * Sizing (D-9): an undated chapter has no slot_count to read its length from,
 * so it is sized by its org-breakdown `derived_teaching_days` when available,
 * else a 5-period (one-teaching-week) default.
 *
 * Re-flow (D-5): a drag-reorder or a manual date edit only re-packs DOWNSTREAM
 * (the changed chapter and everything after it); earlier chapters are untouched.
 * `reflowFrom` is a thin wrapper over `autoPack` for that case.
 *
 * Dates are handled in UTC to avoid timezone drift: a `YYYY-MM-DD` string is
 * parsed as `new Date(s + "T00:00:00Z")` and formatted back via
 * `toISOString().slice(0, 10)`. (The repo's no-argless-Date rule is for
 * workflow scripts, not app code; this module takes all dates as explicit ISO
 * strings anyway and never reads the wall clock.)
 */

/** A chapter as the packer sees it. A subset of `ClassPathChapter`. */
export interface PackInput {
  book_chapter_id: string;
  position: number;
  status: "yet_to_start" | "in_progress" | "done";
  start_date: string | null;
  end_date: string | null;
  /** Teaching-period capacity for a dated chapter (0 when undated). */
  slot_count: number;
}

/** One persisted patch: the computed range for a yet-to-start chapter. */
export interface PackResult {
  book_chapter_id: string;
  start_date: string;
  end_date: string;
}

/** Default span (teaching days) for an undated chapter with no org entry — one
 * teaching week (D-9). */
const DEFAULT_PERIODS = 5;

/* -------------------------------------------------------------------------- */
/* Pure UTC date helpers — no library, no wall-clock read.                    */
/* -------------------------------------------------------------------------- */

/** Parse `YYYY-MM-DD` to a UTC Date at midnight. */
function parseISO(s: string): Date {
  return new Date(s + "T00:00:00Z");
}

/** Format a UTC Date back to `YYYY-MM-DD`. */
function formatISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** The next calendar day (UTC), as a new Date. */
function addDay(d: Date): Date {
  const next = new Date(d.getTime());
  next.setUTCDate(next.getUTCDate() + 1);
  return next;
}

/** True when `d` is a teaching day: Mon–Fri and not an effective holiday. */
function isTeachingDay(d: Date, holidays: Set<string>): boolean {
  const dow = d.getUTCDay(); // 0 = Sun, 6 = Sat
  if (dow === 0 || dow === 6) return false;
  return !holidays.has(formatISO(d));
}

/** Advance `d` forward (inclusive) to the first teaching day on/after it. */
function nextTeachingDayOnOrAfter(d: Date, holidays: Set<string>): Date {
  let cur = d;
  while (!isTeachingDay(cur, holidays)) {
    cur = addDay(cur);
  }
  return cur;
}

/** The teaching periods a chapter needs during packing (D-9):
 *   - dated chapter with capacity → its current slot_count;
 *   - else its org-breakdown derived_teaching_days when present;
 *   - else the 5-period default. */
function periodsFor(ch: PackInput, orgDays: Map<string, number | null>): number {
  if (ch.start_date && ch.end_date && ch.slot_count > 0) {
    return ch.slot_count;
  }
  const org = orgDays.get(ch.book_chapter_id);
  return org ?? DEFAULT_PERIODS;
}

/* -------------------------------------------------------------------------- */
/* Core packer.                                                               */
/* -------------------------------------------------------------------------- */

/**
 * Lay out every yet-to-start chapter back-to-back from `anchor`, holiday-aware.
 *
 * @param chapters  the full path (locked + yet-to-start), any order.
 * @param anchor    the `YYYY-MM-DD` the teacher chose to pack from.
 * @param holidays  effective non-teaching dates (`YYYY-MM-DD`).
 * @param orgDays   `book_chapter_id → derived_teaching_days` from the org
 *                  breakdown (D-9); a null value means "no org span".
 * @returns one `PackResult` per yet-to-start chapter, in position order.
 *          Locked chapters are excluded (D-6).
 *
 * Cursor seeding (D-6): if any chapter is locked, packing starts the day AFTER
 * the last locked chapter's end_date; else at `anchor`. v1 treats the
 * yet-to-start chapters as a contiguous tail packed after the last locked
 * chapter — even if a locked chapter sits between yet-to-start ones, the tail
 * flows forward from the single cursor (D-6's "contiguous tail" framing).
 */
export function autoPack(
  chapters: PackInput[],
  anchor: string,
  holidays: Set<string>,
  orgDays: Map<string, number | null>,
): PackResult[] {
  // Position order is the canonical teaching order.
  const sorted = [...chapters].sort((a, b) => a.position - b.position);

  const locked = sorted.filter((c) => c.status !== "yet_to_start");
  const yetToStart = sorted.filter((c) => c.status === "yet_to_start");

  // D-6: seed the cursor after the LAST locked chapter's end_date (the latest
  // end across all locked chapters, in case positions and dates disagree), else
  // at the teacher's anchor. A locked chapter with no end_date can't extend the
  // cursor, so it's ignored for seeding.
  let cursor: Date;
  const lockedEnds = locked
    .map((c) => c.end_date)
    .filter((e): e is string => !!e);
  if (lockedEnds.length > 0) {
    const lastEnd = lockedEnds.reduce((max, e) => (e > max ? e : max));
    cursor = addDay(parseISO(lastEnd));
  } else {
    cursor = parseISO(anchor);
  }

  const results: PackResult[] = [];
  for (const ch of yetToStart) {
    const periodsNeeded = periodsFor(ch, orgDays);

    // start_date = the next teaching day on/after the cursor — a chapter never
    // starts on a weekend or effective holiday.
    const start = nextTeachingDayOnOrAfter(cursor, holidays);

    // Walk forward counting teaching days until `periodsNeeded` accumulate; the
    // last counted teaching day is the end_date. `start` is teaching day #1.
    let counted = 1;
    let end = start;
    while (counted < periodsNeeded) {
      end = nextTeachingDayOnOrAfter(addDay(end), holidays);
      counted += 1;
    }

    results.push({
      book_chapter_id: ch.book_chapter_id,
      start_date: formatISO(start),
      end_date: formatISO(end),
    });

    // The next chapter's cursor is the day after this end — `autoPack` re-skips
    // to the next teaching day on the next iteration, so back-to-back chapters
    // never overlap and leave no teaching-day gap.
    cursor = addDay(end);
  }

  return results;
}

/**
 * Re-flow the yet-to-start chapters AT AND AFTER `fromBookChapterId`, leaving
 * everything before it (locked or already-dated yet-to-start) untouched
 * (D-5: downstream only). For F2.2 drag re-flow and F2.3 manual-edit downstream
 * re-flow.
 *
 * Cursor seed: the chapter BEFORE the from-chapter (by position) anchors the
 * cursor at the day after its end_date; if `fromBookChapterId` is the first
 * chapter, its own existing start_date seeds the cursor (so a manual pin on the
 * first chapter is respected and the tail flows after it). Falls back to today
 * (passed in via `anchor`) only when neither is available.
 *
 * This is a thin wrapper over `autoPack`: it builds a synthetic chapter list
 * where everything strictly before the from-chapter is treated as "locked" (so
 * autoPack excludes it and seeds the cursor after it), and the from-chapter and
 * everything after it are the yet-to-start tail to repack.
 */
export function reflowFrom(
  chapters: PackInput[],
  fromBookChapterId: string,
  holidays: Set<string>,
  orgDays: Map<string, number | null>,
): PackResult[] {
  const sorted = [...chapters].sort((a, b) => a.position - b.position);
  const fromIdx = sorted.findIndex(
    (c) => c.book_chapter_id === fromBookChapterId,
  );
  // Unknown chapter → nothing to re-flow.
  if (fromIdx === -1) return [];

  const fromCh = sorted[fromIdx];

  // Seed cursor (D-5 downstream-only):
  //   - if there's a chapter before the from-chapter, start the day after its
  //     end_date (the from-chapter must follow it);
  //   - else (from-chapter is first) use its own existing start_date as the
  //     anchor so a pinned first chapter keeps its start.
  let anchor: string;
  const prev = fromIdx > 0 ? sorted[fromIdx - 1] : null;
  if (prev?.end_date) {
    anchor = formatISO(addDay(parseISO(prev.end_date)));
  } else if (fromCh.start_date) {
    anchor = fromCh.start_date;
  } else {
    // No prior end and no existing start: nothing meaningful to seed from.
    // Caller should pass a concrete anchor via autoPack instead; bail safely.
    return [];
  }

  // Treat strictly-earlier chapters as a fixed prefix (status forced non-
  // yet_to_start) so autoPack excludes them and only repacks the tail. We force
  // the prefix's status to "done" purely for autoPack's exclusion logic — but
  // we DON'T want autoPack to re-seed the cursor off their end dates (the prev
  // chapter may be undated). So we drop them entirely and pass the explicit
  // anchor instead; the tail packs cleanly from there.
  const tail = sorted.slice(fromIdx).filter((c) => c.status === "yet_to_start");

  // If the from-chapter itself is locked, there's nothing downstream-editable
  // here that starts at it; pack whatever yet-to-start tail remains from anchor.
  return autoPack(tail, anchor, holidays, orgDays);
}
