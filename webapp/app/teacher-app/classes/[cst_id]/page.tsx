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
  tenancy as tenancyApi,
  today as todayApi,
  type BookChapter,
  type ClassLessonSlotListItem,
  type CstTimelineItem,
  type Holiday,
  type SLO,
  type SubSLOCoverageEntry,
  type SyllabusForCstResponse,
  type TodayEntry,
  type Topic,
} from "@/lib/dars-api";

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

  // async-chapter-plan: break-it-down is async. Dispatch the POST (202 PENDING),
  // then poll plan-status every 3s until READY/ERROR — `busyChapterId` keeps the
  // "Breaking down…" button state live throughout. A 409 means a plan is already
  // generating (e.g. a double-click or another tab), so we just start polling.
  // On READY we refetch the path + timeline + today so the new slots render; on
  // ERROR we surface the planner's error_message.
  const handleBreakDown = useCallback(
    async (book_chapter_id: string) => {
      setSyllabusError(null);
      setBusyChapterId(book_chapter_id);
      try {
        try {
          await slotsApi.breakDownChapter(cstId, book_chapter_id);
        } catch (err) {
          // 409 → a plan is already in flight; fall through to polling. Any
          // other error (422 no-dates / not-in-path / already-broken-down) is a
          // real failure to surface.
          if (!(err instanceof DarsApiError && err.status === 409)) {
            throw err;
          }
        }

        // Poll until the background job lands (mirrors the LP/exam poll loop).
        const POLL_MS = 3000;
        const MAX_POLLS = 60;
        let polls = 0;
        let status: string = "PENDING";
        let errorMessage: string | null = null;
        while (status !== "READY" && status !== "ERROR" && polls < MAX_POLLS) {
          await new Promise((r) => setTimeout(r, POLL_MS));
          polls += 1;
          const s = await slotsApi.getChapterPlanStatus(cstId, book_chapter_id);
          status = s.status;
          errorMessage = s.error_message;
        }

        if (status === "ERROR") {
          setSyllabusError(
            errorMessage ?? "chapter plan generation failed; please retry",
          );
          // Still refresh the path so the chapter's derived state is accurate.
          await loadSyllabus();
          return;
        }
        if (status !== "READY") {
          setSyllabusError(
            "chapter plan is taking longer than expected; refresh to check again",
          );
          return;
        }

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

  const handlePick = useCallback(
    (book_chapter_id: string) =>
      runPathMutation(() => slotsApi.pickChapter(cstId, book_chapter_id)),
    [cstId, runPathMutation],
  );

  const handleSetDates = useCallback(
    (
      book_chapter_id: string,
      dates: { start_date?: string; end_date?: string },
    ) =>
      runPathMutation(() =>
        slotsApi.setChapterDates(cstId, book_chapter_id, dates),
      ),
    [cstId, runPathMutation],
  );

  const handleReorder = useCallback(
    (book_chapter_ids: string[]) =>
      runPathMutation(() => slotsApi.reorderChapters(cstId, book_chapter_ids)),
    [cstId, runPathMutation],
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

  // Today tab: generate today's lesson LP. Navigate to the dedicated LP view
  // page (teacher-app-lp-view-polling F-1.6 / D-8), which auto-starts
  // generation and polls every 5s — "open the lesson plan right then and
  // there." Viewing an already-ready LP still uses the inline slide-over via
  // onViewLP; only the fresh Generate action redirects.
  const onTodayGenerateLP = useCallback(() => {
    const slotId = todayView.todayLessonSlot?.id;
    if (!slotId) return;
    router.push(`/teacher-app/lp/${slotId}`);
  }, [router, todayView.todayLessonSlot?.id]);

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
              generatingLP={false}
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
