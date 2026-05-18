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

import { LPViewer } from "@/components/molecules/lp-viewer";
import { SlideOver } from "@/components/molecules/slide-over";
import {
  ClassAssessmentsTab,
} from "@/components/templates/class-assessments-tab";
import {
  ClassBookTab,
  type BookTabChapter,
  type BookTabTopic,
} from "@/components/templates/class-book-tab";
import {
  ClassDetailTemplate,
  TabEmpty,
  TabError,
  TabLoading,
  type ClassDetailTab,
} from "@/components/templates/class-detail-template";
import {
  ClassLessonsTab,
  type ChapterGroup,
} from "@/components/templates/class-lessons-tab";
import {
  ClassSLOProgressTab,
  type SLOProgressGroup,
} from "@/components/templates/class-slos-tab";
import { ClassTimetableTab } from "@/components/templates/class-timetable-tab";
import {
  DarsApiError,
  books as booksApi,
  curriculum as curriculumApi,
  holidays as holidaysApi,
  progress as progressApi,
  slots as slotsApi,
  tenancy as tenancyApi,
  type BookChapter,
  type ClassAssessmentSlotListItem,
  type ClassLessonSlotListItem,
  type Holiday,
  type SLO,
  type SubSLOCoverageEntry,
  type Topic,
} from "@/lib/dars-api";

const TAB_NAMES: ClassDetailTab[] = [
  "lessons",
  "assessments",
  "timetable",
  "book",
  "slos",
];

function asTab(input: string | null): ClassDetailTab {
  if (input && (TAB_NAMES as string[]).includes(input)) {
    return input as ClassDetailTab;
  }
  return "lessons";
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
          gradeCode: grade?.code ?? "—",
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
  const [lessons, setLessons] = useState<ClassLessonSlotListItem[] | null>(null);
  const [lessonsError, setLessonsError] = useState<string | null>(null);
  const [assessments, setAssessments] = useState<ClassAssessmentSlotListItem[] | null>(null);
  const [assessmentsError, setAssessmentsError] = useState<string | null>(null);
  const [bookChapters, setBookChapters] = useState<BookTabChapter[] | null>(null);
  const [bookError, setBookError] = useState<string | null>(null);
  const [selectedBookChapterId, setSelectedBookChapterId] = useState<string | null>(null);
  const [holidaysData, setHolidaysData] = useState<{
    items: Holiday[];
    effective_dates: string[];
  } | null>(null);
  const [holidaysError, setHolidaysError] = useState<string | null>(null);
  const [holidayBusy, setHolidayBusy] = useState(false);
  const [sloGroups, setSloGroups] = useState<SLOProgressGroup[] | null>(null);
  const [sloError, setSloError] = useState<string | null>(null);
  const [joinedAtPosition, setJoinedAtPosition] = useState(1);

  // Lessons tab data
  const loadLessons = useCallback(async () => {
    setLessonsError(null);
    try {
      const res = await slotsApi.listLessonSlotsForCST(cstId);
      setLessons(res.items);
    } catch (err) {
      setLessonsError(formatErr(err));
    }
  }, [cstId]);

  // Assessments tab data
  const loadAssessments = useCallback(async () => {
    setAssessmentsError(null);
    try {
      const res = await slotsApi.listAssessmentSlotsForCST(cstId);
      setAssessments(res.items);
    } catch (err) {
      setAssessmentsError(formatErr(err));
    }
  }, [cstId]);

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
      return;
    }
    try {
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
      const gradeId = gradeList.find((g) => g.code === header.gradeCode)?.id;
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
          const merged: SubSLOCoverageEntry[] = subSlos.map((ss) => {
            const hit = coverageBySubSLO.get(ss.id);
            return (
              hit ?? {
                sub_slo_id: ss.id,
                sub_slo_code: ss.code,
                status: "not_taught",
              }
            );
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
    if (activeTab === "lessons" && lessons === null) loadLessons();
    if (activeTab === "assessments" && assessments === null) loadAssessments();
    if (activeTab === "timetable" && holidaysData === null) loadHolidays();
    if (activeTab === "book" && bookChapters === null && header) loadBook();
    if (activeTab === "slos" && sloGroups === null && header) loadSLOs();
  }, [
    activeTab,
    lessons,
    assessments,
    holidaysData,
    bookChapters,
    sloGroups,
    header,
    loadLessons,
    loadAssessments,
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

  // Slot focus from URL — open LP slide-over for the matching slot.
  useEffect(() => {
    if (!slotFocus || !lessons) return;
    const slot = lessons.find((l) => l.id === slotFocus);
    if (slot) {
      setDrawer({
        kind: "lp",
        slotId: slot.id,
        title: slot.slot_type === "revision" ? "Revision LP" : "Lesson plan",
        subtitle: `Day ${slot.position} · ${slot.topic_title ?? "—"}`,
      });
    }
  }, [slotFocus, lessons]);

  const onViewLP = (slot: ClassLessonSlotListItem) => {
    setDrawer({
      kind: "lp",
      slotId: slot.id,
      title: slot.slot_type === "revision" ? "Revision LP" : "Lesson plan",
      subtitle: `Day ${slot.position} · ${slot.topic_title ?? "—"}`,
    });
  };

  const onMarkTaught = async (slot: ClassLessonSlotListItem) => {
    setBusySlotId(slot.id);
    try {
      const today = new Date().toISOString().slice(0, 10);
      await slotsApi.markTaught(slot.id, { taught_on: today });
      await loadLessons();
    } catch (err) {
      setLessonsError(formatErr(err));
    } finally {
      setBusySlotId(null);
    }
  };

  const onSkipLesson = async (slot: ClassLessonSlotListItem) => {
    setBusySlotId(slot.id);
    try {
      const today = new Date().toISOString().slice(0, 10);
      await slotsApi.skipLesson(slot.id, { occurred_on: today });
      await loadLessons();
    } catch (err) {
      setLessonsError(formatErr(err));
    } finally {
      setBusySlotId(null);
    }
  };

  const onViewExam = (slot: ClassAssessmentSlotListItem) => {
    setDrawer({
      kind: "exam",
      slotId: slot.id,
      title: slot.assessment_type === "formative" ? "Formative assessment" : "Summative assessment",
      subtitle: `Day ${slot.position} · ${slot.topic_titles.length} topic${slot.topic_titles.length === 1 ? "" : "s"}`,
    });
  };

  const lessonGroups = useMemo<ChapterGroup[]>(() => {
    if (!lessons) return [];
    const map = new Map<string, ChapterGroup>();
    for (const slot of lessons) {
      const key = slot.breakdown_chapter_id;
      const existing = map.get(key);
      if (existing) {
        existing.slots.push(slot);
      } else {
        map.set(key, {
          chapter_id: slot.breakdown_chapter_id,
          chapter_position: slot.breakdown_chapter_position,
          chapter_title: slot.breakdown_chapter_title,
          slots: [slot],
        });
      }
    }
    return Array.from(map.values()).sort(
      (a, b) => a.chapter_position - b.chapter_position,
    );
  }, [lessons]);

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
        {activeTab === "lessons" ? (
          lessonsError ? (
            <TabError message={lessonsError} />
          ) : lessons === null ? (
            <TabLoading label="Loading lessons…" />
          ) : (
            <ClassLessonsTab
              groups={lessonGroups}
              onViewLP={onViewLP}
              onMarkTaught={onMarkTaught}
              onSkip={onSkipLesson}
              busySlotId={busySlotId}
            />
          )
        ) : null}

        {activeTab === "assessments" ? (
          assessmentsError ? (
            <TabError message={assessmentsError} />
          ) : assessments === null ? (
            <TabLoading label="Loading assessments…" />
          ) : (
            <ClassAssessmentsTab items={assessments} onView={onViewExam} />
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
              body="A book hasn’t been wired to this class’s breakdown yet."
            />
          ) : (
            <ClassBookTab
              chapters={bookChapters}
              selectedChapterId={selectedBookChapterId}
              onSelectChapter={setSelectedBookChapterId}
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
          <ExamPlaceholder slotId={drawer.slotId} />
        ) : null}
      </SlideOver>
    </>
  );
}

function ExamPlaceholder({ slotId }: { slotId: string }) {
  return (
    <div className="rounded-md border border-dars-rule-light bg-dars-parchment-mid p-4 text-sm text-dars-ink">
      <p className="font-medium">Exam viewer coming with F4.13/F4.14.</p>
      <p className="text-xs text-dars-muted mt-2">
        Backend exposes the generated_exam HTML + JSON via the
        generated_exam_id linked to this slot ({slotId.slice(0, 8)}…).
        A dedicated exam viewer + mastery entry form lands next.
      </p>
    </div>
  );
}

function formatErr(err: unknown): string {
  if (err instanceof DarsApiError) {
    return `${err.status}: ${typeof err.detail === "string" ? err.detail : "request failed"}`;
  }
  if (err instanceof Error) return err.message;
  return "Failed to load";
}
