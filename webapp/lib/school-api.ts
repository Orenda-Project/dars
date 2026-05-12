/**
 * Thin typed fetch client for the Dars school API (/api/v1/).
 * Auth: X-API-Key header sourced from localStorage "dars_pef_session".
 */

import { getApiKey } from "./session";

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export interface AcademicYearRead {
  id: string;
  client_id: string;
  name: string;
  start_date: string; // ISO date
  end_date: string;
  created_at: string;
}

export interface AcademicYearListResponse {
  items: AcademicYearRead[];
  total: number;
}

export interface AcademicYearCreate {
  name: string;
  start_date: string;
  end_date: string;
}

export interface HolidayRead {
  id: string;
  client_id: string;
  academic_year_id: string;
  date: string;
  name: string;
}

export interface HolidayListResponse {
  items: HolidayRead[];
  total: number;
}

export interface HolidayCreate {
  date: string;
  name: string;
}

export interface SchoolClassRead {
  id: string;
  client_id: string;
  academic_year_id: string;
  grade: number;
  section: string;
  name: string;
  start_date: string | null;
  end_date: string | null;
  created_at: string;
}

export interface SchoolClassListResponse {
  items: SchoolClassRead[];
  total: number;
}

export interface SchoolClassCreate {
  academic_year_id: string;
  grade: number;
  section: string;
  name: string;
  start_date?: string | null;
  end_date?: string | null;
}

export interface CSTRead {
  id: string;
  client_id: string;
  class_id: string;
  subject: string;
  teacher_id: string | null;
  book_id: string | null;
  created_at: string;
}

export interface SchoolClassWithSubjects extends SchoolClassRead {
  subjects: CSTRead[];
}

export interface CSTCreate {
  subject: string;
  teacher_id?: string | null;
  book_id?: string | null;
}

export interface TimetableSlotRead {
  id: string;
  client_id: string;
  class_subject_teacher_id: string;
  day_of_week: number; // 0=Mon..6=Sun
  start_time: string | null;
  end_time: string | null;
  created_at: string;
}

export interface TimetableResponse {
  items: TimetableSlotRead[];
}

export interface TimetableSetRequest {
  slots: { day_of_week: number; start_time?: string | null; end_time?: string | null }[];
}

export interface ChapterPlanWithDates {
  id: string;
  client_id: string;
  class_subject_teacher_id: string;
  chapter_id: string;
  position: number;
  teaching_days: number;
  created_at: string;
  updated_at: string;
  start_date: string | null;
  end_date: string | null;
}

export interface ChapterPlanListResponse {
  items: ChapterPlanWithDates[];
}

export interface ChapterPlanBulkUpsertRequest {
  plans: { chapter_id: string; position: number; teaching_days: number }[];
}

export interface ClassLessonSlotRead {
  id: string;
  client_id: string;
  class_subject_teacher_id: string;
  chapter_plan_id: string;
  day_number: number;
  lp_type: string;
  title: string;
  lesson_plan_id: string | null;
  status: string; // "planned" | "taught"
  taught_date: string | null;
  created_at: string;
}

export interface ClassLessonSlotListResponse {
  items: ClassLessonSlotRead[];
}

export interface AssessmentSlotRead {
  id: string;
  client_id: string;
  class_subject_teacher_id: string;
  chapter_plan_id: string | null;
  assessment_type: string; // "FA" | "SA"
  scheduled_date: string;
  title: string | null;
  exam_generation_id: string | null;
  status: string; // "scheduled" | "completed" | "skipped"
  created_at: string;
  updated_at: string;
}

export interface AssessmentSlotListResponse {
  items: AssessmentSlotRead[];
}

export interface AssessmentSlotUpdate {
  scheduled_date?: string;
  status?: string;
  title?: string;
}

export interface TodaySlotEntry {
  class_id: string;
  class_name: string;
  subject: string;
  cst_id: string;
  teacher_id: string | null;
  teacher_name: string | null;
  next_planned_slot: ClassLessonSlotRead | null;
  previous_taught_slot: ClassLessonSlotRead | null;
}

// ---------------------------------------------------------------------------
// Core fetch helper
// ---------------------------------------------------------------------------

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function apiFetch<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const key = getApiKey();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };
  if (key) headers["X-API-Key"] = key;

  const res = await fetch(`${BASE}${path}`, { ...init, headers });

  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json() as { detail?: string };
      if (body.detail) msg = String(body.detail);
    } catch {
      // ignore parse errors
    }
    throw new Error(msg);
  }

  // 204 No Content
  if (res.status === 204) return undefined as unknown as T;

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Academic Years
// ---------------------------------------------------------------------------

export function getAcademicYears(): Promise<AcademicYearListResponse> {
  return apiFetch<AcademicYearListResponse>("/api/v1/academic-years");
}

export function createAcademicYear(body: AcademicYearCreate): Promise<AcademicYearRead> {
  return apiFetch<AcademicYearRead>("/api/v1/academic-years", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Holidays
// ---------------------------------------------------------------------------

export function addHoliday(yearId: string, body: HolidayCreate): Promise<HolidayRead> {
  return apiFetch<HolidayRead>(`/api/v1/academic-years/${yearId}/holidays`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getHolidays(yearId: string): Promise<HolidayListResponse> {
  return apiFetch<HolidayListResponse>(`/api/v1/academic-years/${yearId}/holidays`);
}

export function deleteHoliday(yearId: string, holidayId: string): Promise<void> {
  return apiFetch<void>(
    `/api/v1/academic-years/${yearId}/holidays/${holidayId}`,
    { method: "DELETE" }
  );
}

// ---------------------------------------------------------------------------
// Classes
// ---------------------------------------------------------------------------

export function getClasses(academicYearId?: string): Promise<SchoolClassListResponse> {
  const qs = academicYearId ? `?academic_year_id=${academicYearId}` : "";
  return apiFetch<SchoolClassListResponse>(`/api/v1/classes${qs}`);
}

export function createClass(body: SchoolClassCreate): Promise<SchoolClassRead> {
  return apiFetch<SchoolClassRead>("/api/v1/classes", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getClass(classId: string): Promise<SchoolClassWithSubjects> {
  return apiFetch<SchoolClassWithSubjects>(`/api/v1/classes/${classId}`);
}

// ---------------------------------------------------------------------------
// Subjects (CST)
// ---------------------------------------------------------------------------

export function assignSubject(classId: string, body: CSTCreate): Promise<CSTRead> {
  return apiFetch<CSTRead>(`/api/v1/classes/${classId}/subjects`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Timetable
// ---------------------------------------------------------------------------

export function setTimetable(
  classId: string,
  cstId: string,
  body: TimetableSetRequest
): Promise<TimetableResponse> {
  return apiFetch<TimetableResponse>(
    `/api/v1/classes/${classId}/subjects/${cstId}/timetable`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

export function getTimetable(classId: string, cstId: string): Promise<TimetableResponse> {
  return apiFetch<TimetableResponse>(
    `/api/v1/classes/${classId}/subjects/${cstId}/timetable`
  );
}

// ---------------------------------------------------------------------------
// Chapter Plans
// ---------------------------------------------------------------------------

export function getChapterPlans(classId: string, cstId: string): Promise<ChapterPlanListResponse> {
  return apiFetch<ChapterPlanListResponse>(
    `/api/v1/classes/${classId}/subjects/${cstId}/chapter-plans`
  );
}

export function upsertChapterPlans(
  classId: string,
  cstId: string,
  body: ChapterPlanBulkUpsertRequest
): Promise<ChapterPlanListResponse> {
  return apiFetch<ChapterPlanListResponse>(
    `/api/v1/classes/${classId}/subjects/${cstId}/chapter-plans`,
    { method: "POST", body: JSON.stringify(body) }
  );
}

// ---------------------------------------------------------------------------
// Lesson Slots
// ---------------------------------------------------------------------------

export function generateLessonSlots(chapterPlanId: string): Promise<ClassLessonSlotListResponse> {
  return apiFetch<ClassLessonSlotListResponse>(
    `/api/v1/chapter-plans/${chapterPlanId}/lesson-slots/generate`,
    { method: "POST" }
  );
}

export function getLessonSlots(chapterPlanId: string): Promise<ClassLessonSlotListResponse> {
  return apiFetch<ClassLessonSlotListResponse>(
    `/api/v1/chapter-plans/${chapterPlanId}/lesson-slots`
  );
}

export function markTaught(slotId: string): Promise<ClassLessonSlotRead> {
  return apiFetch<ClassLessonSlotRead>(
    `/api/v1/class-lesson-slots/${slotId}/mark-taught`,
    { method: "PATCH" }
  );
}

// ---------------------------------------------------------------------------
// Assessment Slots
// ---------------------------------------------------------------------------

export function autoScheduleFAs(classId: string, cstId: string): Promise<AssessmentSlotListResponse> {
  return apiFetch<AssessmentSlotListResponse>(
    `/api/v1/classes/${classId}/subjects/${cstId}/assessment-slots/auto-schedule`,
    { method: "POST" }
  );
}

export function getAssessmentSlots(classId: string, cstId: string): Promise<AssessmentSlotListResponse> {
  return apiFetch<AssessmentSlotListResponse>(
    `/api/v1/classes/${classId}/subjects/${cstId}/assessment-slots`
  );
}

export function updateAssessmentSlot(
  slotId: string,
  body: AssessmentSlotUpdate
): Promise<AssessmentSlotRead> {
  return apiFetch<AssessmentSlotRead>(
    `/api/v1/assessment-slots/${slotId}`,
    { method: "PATCH", body: JSON.stringify(body) }
  );
}

// ---------------------------------------------------------------------------
// Today
// ---------------------------------------------------------------------------

export function getToday(): Promise<TodaySlotEntry[]> {
  return apiFetch<TodaySlotEntry[]>("/api/v1/today");
}
