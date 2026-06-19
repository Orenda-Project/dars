/**
 * F4.6..F4.10 — Class detail page.
 *
 * Owns data fetching for the active tab (lazy: only fetches what the
 * selected tab needs), mark-taught/skip, holiday-override submission,
 * and LP/exam slide-over state.
 */
"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";

import { ExamViewer } from "@/components/molecules/exam-viewer";
import { LPViewer } from "@/components/molecules/lp-viewer";
import { SlideOver } from "@/components/molecules/slide-over";
import {
  ClassBookTab,
  type BookTabChapter,
  type BookTabTopic,
  type TopicSubSLOState,
} from "@/components/templates/class-book-tab";
import {
  ClassDetailTemplate,
  TabEmpty,
  TabError,
  TabLoading,
  type ClassDetailTab,
} from "@/components/templates/class-detail-template";
import {
  ClassSLOProgressTab,
  type SLOProgressGroup,
  type SLOTreeSubSLO,
} from "@/components/templates/class-slos-tab";
import {
  ClassSyllabusTab,
  type BookChapterOption,
} from "@/components/templates/class-syllabus-tab";
import { ClassTimetableTab } from "@/components/templates/class-timetable-tab";
import {
  ClassTodayTab,
  type ProgressSlot,
  type TodayWork,
} from "@/components/templates/class-today-tab";
import {
  DarsApiError,
  books as booksApi,
  curriculum as curriculumApi,
  holidays as holidaysApi,
  progress as progressApi,
  slots as slotsApi,
  syllabusBreakdowns as breakdownsApi,
  tenancy as tenancyApi,
  today as todayApi,
  type BookChapter,
  type ClassPathChapter,
  type ClassLessonSlotListItem,
  type CstTimelineItem,
  type Holiday,
  type SLO,
  type SubSLOCoverageEntry,
  type SyllabusForCstResponse,
  type TodayEntry,
  type Topic,
} from "@/lib/dars-api";
import {
  autoPack,
  reflowFrom,
  type PackInput,
} from "@/lib/planner-pack";

const TAB_NAMES: ClassDetailTab[] = [
  "today",
  "syllabus",
  "timetable",
  "book",
  "slos",
];

function asTab(input: string | null): ClassDetailTab {
  // The Lessons + Assessments tabs (and the later unified Timeline tab) were
  // retired — the Syllabus tab now expands each chapter to show its lessons +
  // assessments in place. Old deep links fall back to it.
  if (input === "lessons" || input === "assessments" || input === "timeline") {
    return "syllabus";
  }
  if (input && (TAB_NAMES as string[]).includes(input)) {
    return input as ClassDetailTab;
  }
  return "today";
}

export default function ClassDetailPage() {
  const params = useParams<{ cst_id: string }>();
  const cstId = params.cst_id;
  const searchParams = useSearchParams();
  const router = useRouter();

  const activeTab = asTab(searchParams.get("tab"));
  const slotFocus = searchParams.get("slot");

  // Header data — resolved once.
  const [headerError, setHeaderError] = useState<string | null>(null);
  const [header, setHeader] = useState<{
    className: string;
    schoolName: string;
    subjectCode: string;
    gradeCode: string;
    bookId: string | null;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cst = await tenancyApi.getCST(cstId);
        const [
          { items: schools },
          { items: classes },
          { items: subjects },
          { items: grades },
        ] = await Promise.all([
          tenancyApi.getSchools(),
          tenancyApi.getClasses(),
          curriculumApi.getSubjects(),
          curriculumApi.getGrades(),
        ]);
        if (cancelled) return;
        const klass = classes.find((c) => c.id === cst.school_class_id);
        const grade = klass ? grades.find((g) => g.id === klass.grade_id) : undefined;
        const school = klass ? schools.find((s) => s.id === klass.school_id) : undefined;
        const subject = subjects.find((s) => s.id === cst.subject_id);
        setHeader({
          className: klass?.name ?? `Class ${cstId.slice(0, 8)}`,
          schoolName: school?.name ?? "—",
          subjectCode: subject?.code ?? "—",
          gradeCode: grade?.code != null ? String(grade.code) : "—",
          bookId: cst.book_id ?? null,
        });
      } catch (err) {
        if (cancelled) return;
        setHeaderError(formatErr(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [cstId]);

  // ----- Tab data state (lazy per tab) -----
  // Lessons list still backs the Today tab (covered/now/next + coverage).
  const [lessons, setLessons] = useState<ClassLessonSlotListItem[] | null>(null);
  // Merged lessons + assessments, dated by the projector. Backs the Syllabus
  // tab's expandable chapter contents (and pins the "Now" marker).
  const [timeline, setTimeline] = useState<CstTimelineItem[] | null>(null);
  const [timelineError, setTimelineError] = useState<string | null>(null);
  // Syllabus tab: the class teaching path. Auto-seeded server-side from the org
  // breakdown (D-10); the teacher edits it on top in Edit mode (D-9/D-13) —
  // re-date, reorder, remove, add. Viewing a chapter's lessons + assessments
  // now happens on the dedicated Chapter Page (lp-context-header D-8/D-12), not
  // an inline accordion.
  const [syllabus, setSyllabus] = useState<SyllabusForCstResponse | null>(null);
  const [syllabusError, setSyllabusError] = useState<string | null>(null);
  const [busyChapterId, setBusyChapterId] = useState<string | null>(null);
  // D-13: explicit Edit-syllabus mode toggle, owned here (template is prop-driven).
  const [editingSyllabus, setEditingSyllabus] = useState(false);
  // Set while any path mutation (pick/set-dates/reorder/remove) is in flight.
  const [pathBusy, setPathBusy] = useState(false);
  // F2.1/D-9: org-breakdown teaching-day spans, keyed by book_chapter_id, used
  // to size UNDATED chapters during auto-pack. Lazily fetched once (on first
  // auto-pack) via the syllabus's syllabus_breakdown_id; null until then. A null
  // map value means "the org has no span for this chapter" → 5-period default.
  const [orgDays, setOrgDays] = useState<Map<string, number | null> | null>(
    null,
  );
  // Flat book-chapter list for the add-a-chapter picker (lazy, edit-mode only).
  const [pickerChapters, setPickerChapters] = useState<BookChapterOption[] | null>(
    null,
  );
  const [bookChapters, setBookChapters] = useState<BookTabChapter[] | null>(null);
  const [bookPdfUrl, setBookPdfUrl] = useState<string | null>(null);
  const [bookError, setBookError] = useState<string | null>(null);
  const [selectedBookChapterId, setSelectedBookChapterId] = useState<string | null>(null);
  // Lazy per-topic sub-SLO cache. Fetched only when a topic row is
  // expanded; second expansion is instant from the map.
  const [expandedTopicId, setExpandedTopicId] = useState<string | null>(null);
  const [topicSubSLOs, setTopicSubSLOs] = useState<Record<string, TopicSubSLOState>>({});
  const [holidaysData, setHolidaysData] = useState<{
    items: Holiday[];
    effective_dates: string[];
  } | null>(null);
  // F1.1 (D-3): effective non-teaching dates as a Set for O(1) membership. Used
  // both by the Syllabus tab's holiday-in-range hint and by Phase-2 packing math
  // (skip weekends + effective holidays). Declared here — before the auto-pack /
  // re-flow handlers that depend on it — so it's in scope for their closures.
  // Empty set while holidays are loading / absent, so callers never null-crash.
  const effectiveHolidays = useMemo<Set<string>>(
    () => new Set(holidaysData?.effective_dates ?? []),
    [holidaysData],
  );
  const [holidaysError, setHolidaysError] = useState<string | null>(null);
  const [holidayBusy, setHolidayBusy] = useState(false);
  const [sloGroups, setSloGroups] = useState<SLOProgressGroup[] | null>(null);
  const [sloError, setSloError] = useState<string | null>(null);
  const [joinedAtPosition, setJoinedAtPosition] = useState(1);

  // Today tab data
  const [todayEntry, setTodayEntry] = useState<TodayEntry | null>(null);
  const [todayLoaded, setTodayLoaded] = useState(false);
  const [todayError, setTodayError] = useState<string | null>(null);
  const [todayCoverage, setTodayCoverage] = useState<{
    taught: number;
    total: number;
  } | null>(null);

  // Today tab data — today's slot for this CST + a coverage tally. The
  // covered/now/next strip is derived from the lessons list, so trigger
  // loadLessons() too.
  const loadToday = useCallback(async () => {
    setTodayError(null);
    try {
      const [todayRes, coverageRes] = await Promise.all([
        todayApi.get(),
        progressApi.getSubSLOCoverage(cstId),
      ]);
      const entry = todayRes.items.find((e) => e.cst_id === cstId) ?? null;
      setTodayEntry(entry);
      setTodayCoverage({
        taught: coverageRes.items.filter((c) => c.status === "taught").length,
        total: coverageRes.items.length,
      });
      setTodayLoaded(true);
    } catch (err) {
      setTodayError(formatErr(err));
    }
  }, [cstId]);

  // Lessons list — backs the Today tab's covered/now/next + coverage.
  const loadLessons = useCallback(async () => {
    try {
      const res = await slotsApi.listLessonSlotsForCST(cstId);
      setLessons(res.items);
    } catch {
      /* non-fatal: Today shows its own error via loadToday */
    }
  }, [cstId]);

  // Timeline tab data — one fetch, lessons + assessments interleaved + dated.
  const loadTimeline = useCallback(async () => {
    setTimelineError(null);
    try {
      const res = await slotsApi.getTimeline(cstId);
      setTimeline(res.items);
    } catch (err) {
      setTimelineError(formatErr(err));
    }
  }, [cstId]);

  // Syllabus tab data — the read-only class path (org-decided, auto-seeded).
  const loadSyllabus = useCallback(async () => {
    setSyllabusError(null);
    try {
      const res = await slotsApi.getSyllabus(cstId);
      setSyllabus(res);
    } catch (err) {
      setSyllabusError(formatErr(err));
    }
  }, [cstId]);

  const handleBreakDown = useCallback(
    async (book_chapter_id: string) => {
      setSyllabusError(null);
      setBusyChapterId(book_chapter_id);
      try {
        await slotsApi.breakDownChapter(cstId, book_chapter_id);
        await Promise.all([
          // Re-fetch the path: status + slot_count change after break-down.
          loadSyllabus(),
          // Timeline + Today now have new slots; refetch if already loaded.
          timeline !== null ? loadTimeline() : Promise.resolve(),
          todayLoaded ? loadToday() : Promise.resolve(),
        ]);
      } catch (err) {
        setSyllabusError(formatErr(err));
      } finally {
        setBusyChapterId(null);
      }
    },
    [cstId, loadSyllabus, loadTimeline, timeline, todayLoaded, loadToday],
  );

  // ---- F3.5: class-path edits (pick / set-dates / reorder / remove) --------
  // Each mutation endpoint returns the full updated SyllabusForCstResponse, so
  // we re-render the tab straight from the payload (no extra GET). The Today /
  // timeline tabs reflect path order + dates, so refresh them when loaded.
  const runPathMutation = useCallback(
    async (mutate: () => Promise<SyllabusForCstResponse>) => {
      setSyllabusError(null);
      setPathBusy(true);
      try {
        const res = await mutate();
        setSyllabus(res);
        await Promise.all([
          timeline !== null ? loadTimeline() : Promise.resolve(),
          todayLoaded ? loadToday() : Promise.resolve(),
        ]);
      } catch (err) {
        setSyllabusError(formatErr(err));
        // Re-sync from the server so the inputs reflect persisted state after
        // a rejected edit (e.g. a 422 reorder/remove lock).
        await loadSyllabus();
      } finally {
        setPathBusy(false);
      }
    },
    [timeline, loadTimeline, todayLoaded, loadToday, loadSyllabus],
  );

  // ---- F2.4: sequential repack runner (Phase 2 auto-pack / re-flow) --------
  // Auto-pack and re-flow compute a LIST of per-chapter date patches client-
  // side, then persist them by issuing N `setChapterDates` PATCHes. Each PATCH
  // returns the full updated syllabus, but firing them in parallel races on the
  // server's position/slot_count recompute (D-7) — so we await them strictly IN
  // ORDER, hold `pathBusy` for the whole batch, and render once at the end.
  // Pure client orchestration over the existing PATCH endpoint — no schema or
  // endpoint change (D-2).
  const runPathRepack = useCallback(
    async (
      patches: { book_chapter_id: string; start_date: string; end_date: string }[],
    ) => {
      // Nothing to do (e.g. an all-locked path, or a re-flow with no tail).
      if (patches.length === 0) return;
      setSyllabusError(null);
      setPathBusy(true);
      try {
        // Sequential, not Promise.all (D-7): each PATCH must see the prior
        // one's persisted result so position/slot_count stay coherent. Keep the
        // final response so we set state once after the last call.
        let last: SyllabusForCstResponse | null = null;
        for (const p of patches) {
          last = await slotsApi.setChapterDates(cstId, p.book_chapter_id, {
            start_date: p.start_date,
            end_date: p.end_date,
          });
        }
        if (last) setSyllabus(last);
        // Timeline / Today reflect path dates — refresh whichever is loaded
        // (mirrors runPathMutation). One refresh after the whole batch.
        await Promise.all([
          timeline !== null ? loadTimeline() : Promise.resolve(),
          todayLoaded ? loadToday() : Promise.resolve(),
        ]);
      } catch (err) {
        // Mid-batch failure (D-7): stop, surface the error, and re-sync from the
        // server's ACTUAL state — never leave the UI on a half-applied client
        // guess (some PATCHes landed, the failing one didn't).
        setSyllabusError(formatErr(err));
        await loadSyllabus();
      } finally {
        setPathBusy(false);
      }
    },
    [cstId, timeline, loadTimeline, todayLoaded, loadToday, loadSyllabus],
  );

  // F2.1/D-9: lazily fetch the org breakdown once and build the
  // book_chapter_id → derived_teaching_days map that sizes undated chapters
  // during packing. Returns the map directly (so the first auto-pack can use it
  // immediately without waiting a render for state to settle). No breakdown
  // (unseeded class) → an empty map; every undated chapter then takes the
  // 5-period default. Pure read of the existing breakdown endpoint (D-2).
  const ensureOrgDays = useCallback(
    async (
      breakdownId: string | null,
    ): Promise<Map<string, number | null>> => {
      if (orgDays) return orgDays;
      const built = new Map<string, number | null>();
      if (breakdownId) {
        try {
          const detail = await breakdownsApi.getBreakdown(breakdownId);
          for (const c of detail.chapters) {
            built.set(c.book_chapter_id, c.derived_teaching_days);
          }
        } catch {
          // Non-fatal: a failed breakdown read just means every undated chapter
          // falls back to the 5-period default (D-9). Cache the empty map so we
          // don't re-fetch on every pack.
        }
      }
      setOrgDays(built);
      return built;
    },
    [orgDays],
  );

  // Build the packer's view of the path (subset of ClassPathChapter).
  const toPackInputs = useCallback(
    (chapters: ClassPathChapter[]): PackInput[] =>
      chapters.map((c) => ({
        book_chapter_id: c.book_chapter_id,
        position: c.position,
        status: c.status,
        start_date: c.start_date,
        end_date: c.end_date,
        slot_count: c.slot_count,
      })),
    [],
  );

  // F2.1: auto-pack every yet-to-start chapter back-to-back from the anchor.
  // Compute the date ranges client-side (autoPack — holiday-aware, D-6 lock
  // respected, D-9 sizing) then persist via the F2.4 sequential runner.
  const handleAutoPack = useCallback(
    async (anchor: string) => {
      if (!syllabus) return;
      const map = await ensureOrgDays(syllabus.syllabus_breakdown_id);
      const patches = autoPack(
        toPackInputs(syllabus.chapters),
        anchor,
        effectiveHolidays,
        map,
      );
      await runPathRepack(patches);
    },
    [syllabus, ensureOrgDays, toPackInputs, effectiveHolidays, runPathRepack],
  );

  const handlePick = useCallback(
    (book_chapter_id: string) =>
      runPathMutation(() => slotsApi.pickChapter(cstId, book_chapter_id)),
    [cstId, runPathMutation],
  );

  // F2.3: manual per-chapter date override (the escape hatch) + downstream
  // re-flow. The teacher pins chapter K's date by hand; we persist that single
  // bound (COALESCE on the server keeps the other), then re-flow every
  // yet-to-start chapter AFTER K so the path stays consecutive (D-5: downstream
  // only — chapters before K are untouched). A manual edit that overlaps an
  // EARLIER chapter is NOT auto-resolved: Phase 1's overlap warning surfaces it
  // (D-4/D-5). The whole thing is ONE busy cycle (D-7): the K-PATCH and the
  // tail re-flow PATCHes run sequentially behind a single pathBusy, one final
  // render.
  const handleSetDates = useCallback(
    async (
      book_chapter_id: string,
      dates: { start_date?: string; end_date?: string },
    ) => {
      if (!syllabus) return;
      setSyllabusError(null);
      setPathBusy(true);
      try {
        // 1) Persist the manual bound. The response carries K's new dates +
        //    server-recomputed slot_count for the whole path.
        const afterPatch = await slotsApi.setChapterDates(
          cstId,
          book_chapter_id,
          dates,
        );
        // 2) Re-flow the yet-to-start tail strictly AFTER K, seeding the cursor
        //    from K's (now-persisted) end_date (D-5). reflowFrom needs the tail
        //    starting at the chapter after K — so we call it on the chapter
        //    right after K in position order; if K is the last chapter there's
        //    no tail and we skip.
        const map = await ensureOrgDays(afterPatch.syllabus_breakdown_id);
        const ordered = [...afterPatch.chapters].sort(
          (a, b) => a.position - b.position,
        );
        const kIdx = ordered.findIndex(
          (c) => c.book_chapter_id === book_chapter_id,
        );
        const next = kIdx >= 0 ? ordered[kIdx + 1] : undefined;
        const patches =
          next && next.status === "yet_to_start"
            ? reflowFrom(
                toPackInputs(ordered),
                next.book_chapter_id,
                effectiveHolidays,
                map,
              )
            : [];

        // 3) Apply the downstream patches sequentially (D-7); if none, the
        //    afterPatch response is already the final state.
        let last: SyllabusForCstResponse = afterPatch;
        for (const p of patches) {
          last = await slotsApi.setChapterDates(cstId, p.book_chapter_id, {
            start_date: p.start_date,
            end_date: p.end_date,
          });
        }
        setSyllabus(last);
        await Promise.all([
          timeline !== null ? loadTimeline() : Promise.resolve(),
          todayLoaded ? loadToday() : Promise.resolve(),
        ]);
      } catch (err) {
        setSyllabusError(formatErr(err));
        await loadSyllabus();
      } finally {
        setPathBusy(false);
      }
    },
    [
      cstId,
      syllabus,
      ensureOrgDays,
      toPackInputs,
      effectiveHolidays,
      timeline,
      loadTimeline,
      todayLoaded,
      loadToday,
      loadSyllabus,
    ],
  );

  const handleReorder = useCallback(
    (book_chapter_ids: string[]) =>
      runPathMutation(() => slotsApi.reorderChapters(cstId, book_chapter_ids)),
    [cstId, runPathMutation],
  );

  // F2.2: drag-to-reorder commits the new order + re-flows the yet-to-start
  // tail's dates. The template computes the new ordered book_chapter_id[] on
  // drop and emits it here; orchestration lives in the page (layering). Two
  // steps, one busy cycle:
  //   1) reorderChapters (PUT) — the server enforces the D-6 lock (422 if it
  //      moves a started chapter) and returns the updated path with new
  //      positions.
  //   2) re-flow: re-pack every yet-to-start chapter from the anchor so the new
  //      order gets consecutive dates (reorder alone only changes position —
  //      D-5 keeps dates consistent with the order). The anchor mirrors F2.1:
  //      day after the last locked chapter, else earliest existing start, else
  //      today; autoPack itself re-seeds after locked chapters (D-6).
  const handleReorderAndReflow = useCallback(
    async (book_chapter_ids: string[]) => {
      setSyllabusError(null);
      setPathBusy(true);
      try {
        // 1) Persist the new order. On a 422 (illegal move past a lock) the
        //    catch re-syncs from the server (mirrors runPathMutation).
        const reordered = await slotsApi.reorderChapters(cstId, book_chapter_ids);
        // 2) Re-flow the tail in the NEW order. autoPack handles the D-6 lock
        //    seeding internally; the anchor is only used when nothing is locked.
        const map = await ensureOrgDays(reordered.syllabus_breakdown_id);
        const anchor = computeAnchor(reordered.chapters);
        const patches = autoPack(
          toPackInputs(reordered.chapters),
          anchor,
          effectiveHolidays,
          map,
        );
        let last: SyllabusForCstResponse = reordered;
        for (const p of patches) {
          last = await slotsApi.setChapterDates(cstId, p.book_chapter_id, {
            start_date: p.start_date,
            end_date: p.end_date,
          });
        }
        setSyllabus(last);
        await Promise.all([
          timeline !== null ? loadTimeline() : Promise.resolve(),
          todayLoaded ? loadToday() : Promise.resolve(),
        ]);
      } catch (err) {
        setSyllabusError(formatErr(err));
        await loadSyllabus();
      } finally {
        setPathBusy(false);
      }
    },
    [
      cstId,
      ensureOrgDays,
      toPackInputs,
      effectiveHolidays,
      timeline,
      loadTimeline,
      todayLoaded,
      loadToday,
      loadSyllabus,
    ],
  );

  const handleRemove = useCallback(
    (book_chapter_id: string) =>
      runPathMutation(() => slotsApi.removeChapter(cstId, book_chapter_id)),
    [cstId, runPathMutation],
  );

  // Lazy flat book-chapter list for the add-a-chapter picker (D-13). Fetched
  // once when edit mode is first entered and the book is known.
  const loadPickerChapters = useCallback(async () => {
    if (!header?.bookId) {
      setPickerChapters([]);
      return;
    }
    try {
      const { items } = await booksApi.getBookChapters(header.bookId);
      setPickerChapters(
        [...items]
          .sort((a, b) => a.chapter_number - b.chapter_number)
          .map<BookChapterOption>((c) => ({
            book_chapter_id: c.id,
            chapter_number: c.chapter_number,
            title: c.title,
          })),
      );
    } catch {
      // Picker is non-critical; leave it null so the panel shows "Loading…".
      setPickerChapters([]);
    }
  }, [header?.bookId]);

  const onToggleEditSyllabus = useCallback(() => {
    setEditingSyllabus((prev) => {
      const next = !prev;
      // Lazy-load the picker the first time edit mode opens.
      if (next && pickerChapters === null) void loadPickerChapters();
      return next;
    });
  }, [pickerChapters, loadPickerChapters]);

  // Holidays tab data
  const loadHolidays = useCallback(async () => {
    setHolidaysError(null);
    try {
      const res = await holidaysApi.getCSTHolidays(cstId);
      setHolidaysData({ items: res.items, effective_dates: res.effective_dates });
    } catch (err) {
      setHolidaysError(formatErr(err));
    }
  }, [cstId]);

  const onAddHolidayOverride = useCallback(
    async (body: { date: string; name?: string; action: "add" | "remove" }) => {
      setHolidayBusy(true);
      try {
        await holidaysApi.addCSTOverride(cstId, body);
        await loadHolidays();
      } finally {
        setHolidayBusy(false);
      }
    },
    [cstId, loadHolidays],
  );

  // Book tab data
  const loadBook = useCallback(async () => {
    setBookError(null);
    if (!header?.bookId) {
      setBookChapters([]);
      setBookPdfUrl(null);
      return;
    }
    try {
      // Book-level metadata (pdf_url) alongside the chapter list. Non-fatal:
      // a missing/failed book fetch just hides the PDF link, never blocks the tab.
      booksApi
        .getBook(header.bookId)
        .then((book) => setBookPdfUrl(book.pdf_url ?? null))
        .catch(() => setBookPdfUrl(null));
      const { items: chapters } = await booksApi.getBookChapters(header.bookId);
      const sorted = [...chapters].sort((a, b) => a.chapter_number - b.chapter_number);
      const fetched = await Promise.all(
        sorted.map(async (ch: BookChapter) => {
          const { items: topics } = await booksApi.getTopics(ch.id);
          const sortedTopics = [...topics].sort((a, b) => a.topic_number - b.topic_number);
          return { chapter: ch, topics: sortedTopics };
        }),
      );

      // Coverage: pull the CST's sub-SLO coverage once and map per topic.
      const coverageRes = await progressApi.getSubSLOCoverage(cstId);
      const taught = new Set(
        coverageRes.items.filter((c) => c.status === "taught").map((c) => c.sub_slo_id),
      );
      const total = new Map<string, { taughtCount: number; total: number }>();
      // For each topic, fetch its sub-SLOs lazily? Too many round-trips.
      // Instead approximate using coverage report which is per-cst.
      // (Per-topic granularity needs server help in Phase 5; this is OK for v1.)
      const result: BookTabChapter[] = fetched.map(({ chapter, topics }) => ({
        chapter,
        topics: topics.map<BookTabTopic>((t: Topic) => ({
          topic: t,
          coverage: null,
        })),
      }));
      setBookChapters(result);
      if (!selectedBookChapterId && result[0]) {
        setSelectedBookChapterId(result[0].chapter.id);
      }
      // Suppress unused-variable warnings for derived sets that v1 doesn't
      // surface per-topic (kept for the Phase 5 expansion).
      void taught;
      void total;
    } catch (err) {
      setBookError(formatErr(err));
    }
  }, [cstId, header?.bookId, selectedBookChapterId]);

  // Lazy fetch sub-SLOs for a single topic; cached by topic_id so repeat
  // expansions hit the map instead of the network. Collapse just flips
  // expandedTopicId; the cache survives so re-expand is instant.
  const onToggleTopic = useCallback(
    (topic_id: string) => {
      setExpandedTopicId((prev) => (prev === topic_id ? null : topic_id));
      setTopicSubSLOs((prev) => {
        if (prev[topic_id]) return prev; // already loading / loaded / errored
        // Kick the fetch outside the setter; the loading marker we
        // return below guards against StrictMode's double-invoke.
        (async () => {
          try {
            const res = await booksApi.getTopicSubSLOs(topic_id);
            setTopicSubSLOs((curr) => ({
              ...curr,
              [topic_id]: { state: "loaded", items: res.items },
            }));
          } catch (err) {
            setTopicSubSLOs((curr) => ({
              ...curr,
              [topic_id]: { state: "error", error: formatErr(err) },
            }));
          }
        })();
        return { ...prev, [topic_id]: { state: "loading" } };
      });
    },
    [],
  );

  // SLO tab data
  const loadSLOs = useCallback(async () => {
    setSloError(null);
    if (!header) return;
    try {
      const coverageRes = await progressApi.getSubSLOCoverage(cstId);
      setJoinedAtPosition(coverageRes.joined_at_position);

      // Need SLO metadata to group sub-SLOs by parent SLO. Easiest: load
      // the SLO list filtered to this CST's (curriculum, grade, subject)
      // — but curriculum_id isn't on CST. Defer to header's grade /
      // subject and the org's curriculum (loaded via getMyOrg).
      const org = await tenancyApi.getMyOrg();
      const { items: subjectList } = await curriculumApi.getSubjects();
      const { items: gradeList } = await curriculumApi.getGrades();
      const subjectId = subjectList.find((s) => s.code === header.subjectCode)?.id;
      const gradeId = gradeList.find((g) => String(g.code) === header.gradeCode)?.id;
      if (!subjectId || !gradeId) {
        setSloGroups([]);
        return;
      }
      const { items: slos } = await curriculumApi.getSLOs({
        curriculum_id: org.curriculum_id,
        grade_id: gradeId,
        subject_id: subjectId,
      });

      // For each SLO, fetch its sub-SLOs and pair with coverage entries.
      const coverageBySubSLO = new Map<string, SubSLOCoverageEntry>(
        coverageRes.items.map((c) => [c.sub_slo_id, c]),
      );

      const groups: SLOProgressGroup[] = await Promise.all(
        slos.map(async (slo: SLO) => {
          const { items: subSlos } = await curriculumApi.getSubSLOs(slo.id);
          const merged: SLOTreeSubSLO[] = subSlos.map((ss) => {
            const hit = coverageBySubSLO.get(ss.id);
            return {
              sub_slo_id: ss.id,
              sub_slo_code: ss.code,
              sub_slo_statement: ss.statement,
              status: hit?.status ?? "not_taught",
            };
          });
          return {
            slo_id: slo.id,
            slo_code: slo.code,
            slo_statement: slo.statement,
            sub_slos: merged,
          };
        }),
      );
      setSloGroups(groups);
    } catch (err) {
      setSloError(formatErr(err));
    }
  }, [cstId, header]);

  // Tab-driven loads
  useEffect(() => {
    if (activeTab === "today") {
      if (!todayLoaded) loadToday();
      if (lessons === null) loadLessons();
      // Need the syllabus to show "you should be teaching Ch X" when today has
      // no generated slot yet (chapter not broken down).
      if (syllabus === null) loadSyllabus();
    }
    if (activeTab === "syllabus") {
      if (syllabus === null) loadSyllabus();
      // Chapter rows expand to show their lessons + assessments — load the
      // timeline that backs them. Today entry pins the "Now" marker.
      if (timeline === null) loadTimeline();
      if (!todayLoaded) loadToday();
      // F1.1 (D-3): the planner shows effective holidays inline + uses them for
      // the holiday-in-range hint. Reuse the same cheap, cached getCSTHolidays
      // fetch the Timetable tab uses — no new data, no new endpoint.
      if (holidaysData === null) loadHolidays();
    }
    if (activeTab === "timetable" && holidaysData === null) loadHolidays();
    if (activeTab === "book" && bookChapters === null && header) loadBook();
    if (activeTab === "slos" && sloGroups === null && header) loadSLOs();
  }, [
    activeTab,
    lessons,
    timeline,
    syllabus,
    holidaysData,
    bookChapters,
    sloGroups,
    header,
    todayLoaded,
    loadToday,
    loadLessons,
    loadTimeline,
    loadSyllabus,
    loadHolidays,
    loadBook,
    loadSLOs,
  ]);

  // Slide-over state
  const [drawer, setDrawer] = useState<{
    kind: "lp" | "exam";
    slotId: string;
    title: string;
    subtitle: string;
  } | null>(null);
  const [busySlotId, setBusySlotId] = useState<string | null>(null);
  // Slot whose LP is being generated + polled on-demand (Generate LP button).
  const [generatingSlotId, setGeneratingSlotId] = useState<string | null>(null);
  // FA slot whose exam is being generated + polled (Generate exam button).
  const [generatingExamSlotId, setGeneratingExamSlotId] = useState<string | null>(
    null,
  );

  // Slot focus from URL — open LP slide-over for the matching timeline slot.
  useEffect(() => {
    if (!slotFocus || !timeline) return;
    const slot = timeline.find((t) => t.kind === "lesson" && t.id === slotFocus);
    if (slot && slot.kind === "lesson") openLP(slot);
  }, [slotFocus, timeline]);

  // Chapter positions that already have timeline slots → a plan exists. This is
  // the authoritative "broken down" signal for the Syllabus tab's per-chapter
  // "Generate chapter plan" button, which would otherwise rely on the syllabus
  // payload's `is_generated` flag and keep offering the button for a chapter
  // that already has lessons + assessments. `undefined` until the timeline
  // loads, so the tab falls back to `is_generated` in the meantime.
  const generatedPositions = useMemo<Set<number> | undefined>(() => {
    if (timeline === null) return undefined;
    return new Set(timeline.map((t) => t.breakdown_chapter_position));
  }, [timeline]);

  function openLP(slot: Extract<CstTimelineItem, { kind: "lesson" }>) {
    setDrawer({
      kind: "lp",
      slotId: slot.id,
      title: slot.slot_type === "revision" ? "Revision LP" : "Lesson plan",
      subtitle: `Day ${slot.position} · ${slot.topic_title ?? "—"}`,
    });
  }

  // ---- Lesson-list handlers (Today tab; operate on ClassLessonSlotListItem) ----
  const onViewLPLesson = (slot: ClassLessonSlotListItem) => {
    setDrawer({
      kind: "lp",
      slotId: slot.id,
      title: slot.slot_type === "revision" ? "Revision LP" : "Lesson plan",
      subtitle: `Day ${slot.position} · ${slot.topic_title ?? "—"}`,
    });
  };

  const markTaughtById = useCallback(
    async (slotId: string) => {
      setBusySlotId(slotId);
      try {
        const today = new Date().toISOString().slice(0, 10);
        await slotsApi.markTaught(slotId, { taught_on: today });
        await Promise.all([
          loadLessons(),
          timeline !== null ? loadTimeline() : Promise.resolve(),
          todayLoaded ? loadToday() : Promise.resolve(),
        ]);
      } catch (err) {
        setTimelineError(formatErr(err));
      } finally {
        setBusySlotId(null);
      }
    },
    [loadLessons, loadTimeline, loadToday, timeline, todayLoaded],
  );

  const onMarkTaught = (slot: ClassLessonSlotListItem) => markTaughtById(slot.id);

  // On-demand LP generation for a lesson slot (Generate / Retry).
  // Dispatch, then poll the slot detail until the LP is READY/ERROR,
  // running `refetch` each tick so the relevant tab's status pills update
  // live (and the Generate button swaps to View LP on success). The service
  // is idempotent, so a cache hit returns a terminal status on the first
  // response and we skip polling entirely.
  const generateLPAndPoll = useCallback(
    async (slotId: string, refetch: () => Promise<void>) => {
      setGeneratingSlotId(slotId);
      try {
        const created = await slotsApi.generateLPForSlot(slotId);
        await refetch(); // reflect the new in-flight (or ready) status now

        let status: string = created.lp_status;
        const POLL_MS = 3000;
        const MAX_POLLS = 40; // ~2 min ceiling; webhook usually finishes sooner
        let polls = 0;
        while (status !== "READY" && status !== "ERROR" && polls < MAX_POLLS) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          polls += 1;
          const detail = await slotsApi.getLessonSlotDetail(slotId);
          status = detail.lp_status;
          await refetch(); // keep the status pill in sync as it advances
        }
      } finally {
        setGeneratingSlotId(null);
      }
    },
    [],
  );

  // On-demand FA exam generation for an assessment slot (Generate / Retry).
  // The assessment-slot analogue of generateLPAndPoll: dispatch, then poll
  // the assessment-slot detail until the exam is READY/ERROR, refetching the
  // timeline each tick so the exam status pill + button stay live. The service
  // is idempotent, so a cache hit returns a terminal status immediately and we
  // skip polling.
  const generateExamAndPoll = useCallback(
    async (slotId: string, refetch: () => Promise<void>) => {
      setGeneratingExamSlotId(slotId);
      try {
        const created = await slotsApi.generateExamForSlot(slotId);
        await refetch();

        let status: string = created.exam_status;
        const POLL_MS = 3000;
        const MAX_POLLS = 40; // ~2 min ceiling; webhook usually finishes sooner
        let polls = 0;
        while (status !== "READY" && status !== "ERROR" && polls < MAX_POLLS) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          polls += 1;
          const detail = await slotsApi.getAssessmentSlotDetail(slotId);
          status = detail.exam_status;
          await refetch();
        }
      } finally {
        setGeneratingExamSlotId(null);
      }
    },
    [],
  );

  // Today dashboard derived state — needs the lessons list for covered/now/next
  // and topic titles, plus the today entry to identify today's slot.
  const todayView = useMemo(() => {
    const plannedLessons = (lessons ?? [])
      .filter((l) => l.status === "planned")
      .sort((a, b) => a.position - b.position);

    const todayLessonSlot = todayEntry?.lesson_slot
      ? (lessons ?? []).find((l) => l.id === todayEntry.lesson_slot!.slot_id) ?? null
      : null;

    // Now = today's lesson slot if scheduled, else the next planned lesson (D-3).
    const nowListItem = todayLessonSlot ?? plannedLessons[0] ?? null;
    const nextListItem = nowListItem
      ? plannedLessons.find((l) => l.position > nowListItem.position) ?? null
      : null;

    const toProgressSlot = (
      s: ClassLessonSlotListItem | null,
    ): ProgressSlot | null =>
      s ? { position: s.position, topicTitle: s.topic_title } : null;

    let work: TodayWork = null;
    if (todayLessonSlot) {
      work = {
        kind: "lesson",
        slotId: todayLessonSlot.id,
        position: todayLessonSlot.position,
        slotType: todayLessonSlot.slot_type,
        lpType: todayLessonSlot.lp_type,
        topicTitle: todayLessonSlot.topic_title,
        status: todayLessonSlot.status,
        lpStatus: todayLessonSlot.lp_status,
      };
    } else if (todayEntry?.assessment_slot) {
      const a = todayEntry.assessment_slot;
      work = {
        kind: "assessment",
        slotId: a.slot_id,
        position: a.position,
        assessmentType: a.assessment_type,
        topicCount: a.topic_ids.length,
        // The /today endpoint doesn't surface exam_status; default to
        // not_generated so the card offers "Generate exam". The ExamViewer
        // (and the timeline tab) read the real status when opened. In-flight
        // state on this card is driven by `generatingExam` during the poll.
        examStatus: "not_generated",
      };
    }

    return {
      work,
      todayLessonSlot,
      coveredCount: (lessons ?? []).filter((l) => l.status === "taught").length,
      nowSlot: toProgressSlot(nowListItem),
      nextSlot: toProgressSlot(nextListItem),
    };
  }, [lessons, todayEntry]);

  // Today tab: generate today's lesson LP on demand. The today card's lp
  // status comes from the lessons list, so refetch that (+ the today entry)
  // each poll tick. Defined after todayView so the slot id is resolvable.
  const onTodayGenerateLP = useCallback(async () => {
    const slotId = todayView.todayLessonSlot?.id;
    if (!slotId) return;
    setTodayError(null);
    try {
      await generateLPAndPoll(slotId, async () => {
        await Promise.all([loadLessons(), loadToday()]);
      });
    } catch (err) {
      setTodayError(formatErr(err));
    }
  }, [generateLPAndPoll, loadLessons, loadToday, todayView.todayLessonSlot?.id]);

  // Today tab: generate today's FA exam on demand (the assessment analogue of
  // onTodayGenerateLP). Refetch the today entry each poll tick.
  const onTodayGenerateExam = useCallback(async () => {
    const w = todayView.work;
    if (!w || w.kind !== "assessment") return;
    setTodayError(null);
    try {
      await generateExamAndPoll(w.slotId, loadToday);
    } catch (err) {
      setTodayError(formatErr(err));
    }
  }, [generateExamAndPoll, loadToday, todayView.work]);

  const todayLabel = useMemo(
    () =>
      new Date().toLocaleDateString("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      }),
    [],
  );

  // ---- Render ----
  if (headerError) return <TabError message={headerError} />;
  if (!header) return <TabLoading label="Loading class…" />;

  return (
    <>
      <ClassDetailTemplate
        cstId={cstId}
        activeTab={activeTab}
        className={header.className}
        subjectCode={header.subjectCode}
        gradeCode={header.gradeCode}
        schoolName={header.schoolName}
      >
        {activeTab === "today" ? (
          todayError ? (
            <TabError message={todayError} />
          ) : !todayLoaded || lessons === null ? (
            <TabLoading label="Loading today…" />
          ) : (
            <ClassTodayTab
              todayLabel={todayLabel}
              work={todayView.work}
              coveredCount={todayView.coveredCount}
              nowSlot={todayView.nowSlot}
              nextSlot={todayView.nextSlot}
              coverage={todayCoverage}
              onViewLP={() => {
                if (todayView.todayLessonSlot) onViewLPLesson(todayView.todayLessonSlot);
              }}
              onMarkTaught={() => {
                if (todayView.todayLessonSlot) onMarkTaught(todayView.todayLessonSlot);
              }}
              onGenerateLP={onTodayGenerateLP}
              generatingLP={
                todayView.todayLessonSlot != null &&
                generatingSlotId === todayView.todayLessonSlot.id
              }
              onGenerateExam={onTodayGenerateExam}
              generatingExam={
                todayView.work?.kind === "assessment" &&
                generatingExamSlotId === todayView.work.slotId
              }
              onViewExam={() => {
                const a = todayEntry?.assessment_slot;
                if (a) {
                  setDrawer({
                    kind: "exam",
                    slotId: a.slot_id,
                    title:
                      a.assessment_type === "formative"
                        ? "Formative assessment"
                        : "Summative assessment",
                    subtitle: `Day ${a.position}`,
                  });
                }
              }}
              currentChapterToPlan={(() => {
                // Only relevant when today has no generated slot. Surface the
                // next path chapter the teacher should be teaching whose plan
                // doesn't exist yet. "Plan exists" is `is_generated` (the
                // chapter has class slots) — NOT slot_count, which is just the
                // projected period capacity and is non-zero the moment dates
                // are set. Require capacity (slot_count > 0) + dates so the
                // offered "break it down" has something to size against and
                // won't 422.
                if (todayView.work !== null) return null;
                const c = [...(syllabus?.chapters ?? [])]
                  .sort((a, b) => a.position - b.position)
                  .find(
                    (ch) =>
                      !ch.is_generated &&
                      ch.slot_count > 0 &&
                      ch.start_date != null &&
                      ch.end_date != null,
                  );
                return c
                  ? {
                      bookChapterId: c.book_chapter_id,
                      chapterNumber: c.chapter_number,
                      title: c.title,
                    }
                  : null;
              })()}
              onBreakDown={handleBreakDown}
              busy={busySlotId !== null || busyChapterId !== null}
            />
          )
        ) : null}

        {activeTab === "syllabus" ? (
          syllabusError ? (
            <TabError message={syllabusError} />
          ) : syllabus === null ? (
            <TabLoading label="Loading syllabus…" />
          ) : (
            <>
              {timelineError ? (
                <div className="mb-4">
                  <TabError message={timelineError} />
                </div>
              ) : null}
              <ClassSyllabusTab
                data={syllabus}
                cstId={cstId}
                onBreakDown={handleBreakDown}
                busyChapterId={busyChapterId}
                generatedPositions={generatedPositions}
                editing={editingSyllabus}
                onToggleEdit={onToggleEditSyllabus}
                onPick={handlePick}
                onSetDates={handleSetDates}
                onReorder={handleReorder}
                onRemove={handleRemove}
                bookChapters={pickerChapters}
                pathBusy={pathBusy}
                effectiveHolidays={effectiveHolidays}
                holidayItems={holidaysData?.items ?? []}
                /* F2.1: default anchor (day after last locked chapter, else
                   earliest start, else today) + the auto-pack action. */
                defaultAnchor={computeAnchor(syllabus.chapters)}
                onAutoPack={handleAutoPack}
                /* F2.2: drag-reorder commits the new order then re-flows the
                   yet-to-start tail's dates (orchestrated in the page). */
                onReorderAndReflow={handleReorderAndReflow}
              />
            </>
          )
        ) : null}

        {activeTab === "timetable" ? (
          holidaysError ? (
            <TabError message={holidaysError} />
          ) : holidaysData === null ? (
            <TabLoading label="Loading timetable…" />
          ) : (
            <ClassTimetableTab
              effectiveDates={holidaysData.effective_dates}
              holidays={holidaysData.items}
              busy={holidayBusy}
              onAddOverride={onAddHolidayOverride}
            />
          )
        ) : null}

        {activeTab === "book" ? (
          bookError ? (
            <TabError message={bookError} />
          ) : bookChapters === null ? (
            <TabLoading label="Loading book…" />
          ) : bookChapters.length === 0 ? (
            <TabEmpty
              title="No book linked"
              body="No book is set up for this class yet. Reach out to your administrator."
            />
          ) : (
            <ClassBookTab
              chapters={bookChapters}
              selectedChapterId={selectedBookChapterId}
              onSelectChapter={(id) => {
                setSelectedBookChapterId(id);
                // Collapse any open topic so the expanded panel doesn't
                // hang around when the chapter switches under it.
                setExpandedTopicId(null);
              }}
              expandedTopicId={expandedTopicId}
              onToggleTopic={onToggleTopic}
              topicSubSLOs={topicSubSLOs}
              pdfUrl={bookPdfUrl}
            />
          )
        ) : null}

        {activeTab === "slos" ? (
          sloError ? (
            <TabError message={sloError} />
          ) : sloGroups === null ? (
            <TabLoading label="Loading SLO progress…" />
          ) : (
            <ClassSLOProgressTab
              groups={sloGroups}
              joinedAtPosition={joinedAtPosition}
            />
          )
        ) : null}
      </ClassDetailTemplate>

      <SlideOver
        open={drawer !== null}
        onClose={() => {
          setDrawer(null);
          // Clear ?slot= if present so refresh doesn't re-open.
          if (slotFocus) {
            router.replace(`/teacher-app/classes/${cstId}?tab=${activeTab}`, { scroll: false });
          }
        }}
        title={drawer?.title ?? ""}
        subtitle={drawer?.subtitle}
      >
        {drawer?.kind === "lp" ? <LPViewer slotId={drawer.slotId} /> : null}
        {drawer?.kind === "exam" ? (
          <ExamViewer slotId={drawer.slotId} />
        ) : null}
      </SlideOver>
    </>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed to load";
}

/**
 * F2.1: the default anchor (`YYYY-MM-DD`) the planner packs from (D-1/D-6):
 *   1) the day AFTER the last locked chapter's end_date, if any chapter is
 *      locked (packing resumes after the immutable past — D-6); else
 *   2) the earliest existing start_date in the path (respect a plan already in
 *      progress of being dated); else
 *   3) today.
 * Pure: takes the path + today and returns an ISO string. UTC throughout to
 * avoid TZ drift (matches lib/planner-pack.ts).
 */
function computeAnchor(
  chapters: ClassPathChapter[],
  todayIso: string = new Date().toISOString().slice(0, 10),
): string {
  const addDayIso = (iso: string): string => {
    const d = new Date(iso + "T00:00:00Z");
    d.setUTCDate(d.getUTCDate() + 1);
    return d.toISOString().slice(0, 10);
  };

  // 1) day after the last locked chapter's end_date.
  const lockedEnds = chapters
    .filter((c) => c.status !== "yet_to_start")
    .map((c) => c.end_date)
    .filter((e): e is string => !!e);
  if (lockedEnds.length > 0) {
    const lastEnd = lockedEnds.reduce((max, e) => (e > max ? e : max));
    return addDayIso(lastEnd);
  }

  // 2) earliest existing start_date.
  const starts = chapters
    .map((c) => c.start_date)
    .filter((s): s is string => !!s);
  if (starts.length > 0) {
    return starts.reduce((min, s) => (s < min ? s : min));
  }

  // 3) today.
  return todayIso;
}
