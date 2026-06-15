/**
 * F4.2 — Dars v2 API client.
 *
 * Browser-side fetch wrapper. Reads the per-org API key from
 * localStorage('dars_org_api_key') and sends it as `X-API-Key` on every
 * request that hits a per-org endpoint. Base URL comes from
 * NEXT_PUBLIC_API_URL.
 *
 * The backend currently has TWO prefix conventions:
 *   - /api/v2/*  → Phase 1 + Phase 2 endpoints (tenancy, curriculum, book,
 *                  breakdowns, holidays, class actions, today, calendar)
 *   - /api/v1/*  → Phase 3 endpoints (generation status, usage, webhooks,
 *                  refresh, class-lesson-slot detail)
 * Function-level docs note which prefix each function hits.
 *
 * Endpoints referenced but not yet shipped on the server are flagged
 * with a TODO comment; they're stubbed to throw for now so callers
 * can find them at build time:
 *   - quickLP / quickExam        (F4.14 — `/api/v1/quick-lp`, `/quick-exam`)
 *   - submitExamResults          (F4.13 — `/api/v1/class-assessment-slots/{id}/results`)
 *
 * This module has zero non-stdlib dependencies; tree-shakes cleanly.
 */

// ---------------------------------------------------------------------------
// Shared types
// ---------------------------------------------------------------------------

export type UUID = string;
export type ISODate = string;   // YYYY-MM-DD
export type ISODateTime = string;

export interface ListResponse<T> {
  items: T[];
}

export interface PageListResponse<T> extends ListResponse<T> {
  total?: number;
  limit?: number;
  offset?: number;
}

// ---------------------------------------------------------------------------
// Tenancy
// ---------------------------------------------------------------------------

export interface Org {
  id: UUID;
  name: string;
  curriculum_id: UUID;
  default_teacher_id: UUID | null;
  api_key_prefix: string;
}

export interface School {
  id: UUID;
  org_id: UUID;
  name: string;
}

export interface Teacher {
  id: UUID;
  org_id: UUID;
  school_id: UUID;
  name: string;
  email: string | null;
}

export interface AcademicYear {
  id: UUID;
  org_id: UUID;
  school_id: UUID;
  name: string;
  start_date: ISODate;
  end_date: ISODate;
}

export interface SchoolClass {
  id: UUID;
  org_id: UUID;
  school_id: UUID;
  academic_year_id: UUID;
  grade_id: UUID;
  section: string;
  name: string;
}

/**
 * CST = (class, subject, teacher) tuple. Note the row itself only carries
 * `subject_id` and `school_class_id` directly — `grade_id` / `school_id`
 * live on the joined `school_classes` row; `curriculum_id` is org-level.
 * The list endpoint omits `current_sequence_position`; the single-row
 * GET adds it.
 */
export interface CST {
  id: UUID;
  org_id: UUID;
  school_class_id: UUID;
  teacher_id: UUID | null;
  subject_id: UUID;
  book_id: UUID | null;
  current_sequence_position?: number | null;
}

// ---------------------------------------------------------------------------
// Curriculum
// ---------------------------------------------------------------------------

export interface Curriculum {
  id: UUID;
  code: string;
  name: string;
}

export interface Grade {
  id: UUID;
  code: number;        // 1..12
  display_name: string; // 'Grade 1'..'Grade 12'
}

export interface Subject {
  id: UUID;
  code: string;        // 'Eng' | 'Urdu' | 'Maths' | 'Science' | 'GK' | …
  display_name: string;
}

export interface SLO {
  id: UUID;
  code: string;
  statement: string;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  position: number;
  recommended_lp_type: string | null;
}

export interface SubSLO {
  id: UUID;
  slo_id: UUID;
  code: string;
  statement: string;
  source: string;
}

// ---------------------------------------------------------------------------
// Book
// ---------------------------------------------------------------------------

export interface Book {
  id: UUID;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  title: string;
  publisher?: string | null;
  edition?: string | null;
  published_year?: number | null;
  total_chapters?: number | null;
  pdf_url?: string | null;
  /** Only populated by `?include=book_text` or the tree endpoint; else null. */
  book_text?: BookTextEntry[] | null;
}

/** A page slice of OCR'd book/chapter text — `[{ pdf_page_no, text }, ...]`. */
export type BookTextEntry = Record<string, unknown>;

/**
 * `chapter_text` is a structured page slice — list of objects keyed by
 * page-content type ({ kind, text } pairs etc). It's only populated when
 * the request hits `?include=chapter_text` or the tree endpoint; otherwise null.
 */
export type ChapterTextEntry = Record<string, unknown>;

export interface BookChapter {
  id: UUID;
  book_id: UUID;
  chapter_number: number;
  title: string;
  start_page: number | null;
  end_page: number | null;
  chapter_text: ChapterTextEntry[] | null;
  status: string;
}

export interface Topic {
  id: UUID;
  book_chapter_id: UUID;
  topic_number: number;
  title: string;
  start_line: number | null;
  end_line: number | null;
  topic_text: string | null;
  status: string;
}

/** Minimal SLO / sub-SLO shape returned inside the book tree. */
export interface SLOMini {
  id: UUID;
  code: string;
  statement: string;
}

/** Full nested book tree from `GET /api/v2/books/{id}/tree` (OCR included). */
export interface TopicTree extends Topic {
  sub_slos: SLOMini[];
}

export interface BookChapterTree extends BookChapter {
  slos: SLOMini[];
  topics: TopicTree[];
}

export interface BookTree extends Book {
  chapters: BookChapterTree[];
}

// ---------------------------------------------------------------------------
// Syllabus breakdowns (global-only, chapter date ranges)
// ---------------------------------------------------------------------------

export type SyllabusBreakdownStatus = "draft" | "published" | "deleted";

export interface SyllabusBreakdown {
  id: UUID;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  book_id: UUID | null;
  status: SyllabusBreakdownStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface ClassLessonSlot {
  id: UUID;
  cst_id: UUID;
  position: number;
  slot_type: "lesson" | "revision";
  lp_type: string | null;
  topic_id: UUID | null;
  anchor_date: ISODate | null;
  status: "planned" | "taught" | "skipped";
  generated_lp_id: UUID | null;
}

export interface ClassLessonSlotDetail extends ClassLessonSlot {
  topic_text: string | null;
  chapter_number: number | null;
  chapter_title: string | null;
  lp_status:
    | "not_generated"
    | "PENDING"
    | "IN_FLIGHT"
    | "READY"
    | "ERROR";
  lp_content: string | null;
  lp_error_message: string | null;
  lp_tagging_status: "pending" | "done" | "failed" | null;
  lp_covered_sub_slo_ids: UUID[];
}

/**
 * Returned by `POST /api/v1/class-lesson-slots/{id}/generate-lp`. The
 * `lp_status` mirrors ClassLessonSlotDetail.lp_status (minus
 * `not_generated`, since generation always lands a real status) so the FE
 * can poll getLessonSlotDetail() with the same handling.
 */
export interface GenerateLPResponse {
  generated_lp_id: UUID;
  lp_status: "PENDING" | "IN_FLIGHT" | "READY" | "ERROR";
}

/**
 * Returned by `POST /api/v1/class-assessment-slots/{id}/generate-exam`
 * (F-3.3). The `exam_status` mirrors ClassAssessmentSlotDetail.exam_status
 * (minus `not_generated`) so the FE can poll getAssessmentSlotDetail() with
 * the same handling it uses for LPs.
 */
export interface GenerateExamResponse {
  generated_exam_id: UUID;
  exam_status: "PENDING" | "IN_FLIGHT" | "READY" | "ERROR";
}

export interface ClassAssessmentSlot {
  id: UUID;
  cst_id: UUID;
  position: number;
  assessment_type: "formative" | "summative";
  anchor_date: ISODate | null;
  status: "scheduled" | "completed" | "skipped";
  generated_exam_id: UUID | null;
  topic_ids: UUID[];
}

/**
 * Row returned by `/api/v2/csts/{id}/lesson-slots` — adds chapter context
 * + LP status so the teacher app can render grouped lists without N+1
 * fetches.
 */
export interface ClassLessonSlotListItem {
  id: UUID;
  cst_id: UUID;
  position: number;
  slot_type: "lesson" | "revision";
  lp_type: string | null;
  topic_id: UUID | null;
  topic_title: string | null;
  anchor_date: ISODate | null;
  status: "planned" | "taught" | "skipped";
  generated_lp_id: UUID | null;
  lp_status:
    | "not_generated"
    | "PENDING"
    | "IN_FLIGHT"
    | "READY"
    | "ERROR";
  breakdown_chapter_id: UUID;
  breakdown_chapter_position: number;
  breakdown_chapter_title: string;
}

export interface ClassLessonSlotListResponse {
  cst_id: UUID;
  items: ClassLessonSlotListItem[];
}

export interface ClassAssessmentSlotListItem {
  id: UUID;
  cst_id: UUID;
  position: number;
  assessment_type: "formative" | "summative";
  anchor_date: ISODate | null;
  status: "scheduled" | "completed" | "skipped";
  generated_exam_id: UUID | null;
  exam_status:
    | "not_generated"
    | "PENDING"
    | "IN_FLIGHT"
    | "READY"
    | "ERROR";
  topic_ids: UUID[];
  topic_titles: string[];
  breakdown_chapter_id: UUID;
  breakdown_chapter_position: number;
  breakdown_chapter_title: string;
}

export interface ClassAssessmentSlotListResponse {
  cst_id: UUID;
  items: ClassAssessmentSlotListItem[];
}

/**
 * Unified timeline (class-timeline-view). `/api/v2/csts/{id}/timeline`
 * returns lessons + assessments interleaved by global `position`, each
 * stamped with the projector's `projected_date` + conflict/overflow flags.
 * Discriminated on `kind`.
 */
export type TimelineGenStatus =
  | "not_generated"
  | "PENDING"
  | "IN_FLIGHT"
  | "READY"
  | "ERROR";

export interface TimelineLessonItem {
  kind: "lesson";
  id: UUID;
  position: number;
  projected_date: ISODate | null;
  is_anchor: boolean;
  is_conflict: boolean;
  is_overflow: boolean;
  slot_type: "lesson" | "revision";
  lp_type: string | null;
  topic_id: UUID | null;
  topic_title: string | null;
  status: "planned" | "taught" | "skipped";
  generated_lp_id: UUID | null;
  lp_status: TimelineGenStatus;
  breakdown_chapter_id: UUID;
  breakdown_chapter_position: number;
  breakdown_chapter_title: string;
}

export interface TimelineAssessmentItem {
  kind: "assessment";
  id: UUID;
  position: number;
  projected_date: ISODate | null;
  is_anchor: boolean;
  is_conflict: boolean;
  is_overflow: boolean;
  assessment_type: "formative" | "summative";
  topic_ids: UUID[];
  topic_titles: string[];
  status: "scheduled" | "completed" | "skipped";
  generated_exam_id: UUID | null;
  exam_status: TimelineGenStatus;
  breakdown_chapter_id: UUID;
  breakdown_chapter_position: number;
  breakdown_chapter_title: string;
}

export type CstTimelineItem = TimelineLessonItem | TimelineAssessmentItem;

export interface CstTimelineResponse {
  cst_id: UUID;
  items: CstTimelineItem[];
  /**
   * dynamic-chapter-planner F-1.4: count of tail slots the projector could not
   * land on a teaching day (overflow). 0 ⇒ the plan fits the academic year;
   * > 0 ⇒ the class is genuinely behind (surface a human alert).
   */
  overflow_count?: number;
}

/** Returned by `GET /api/v1/class-assessment-slots/{id}` (F4.13). */
export interface ClassAssessmentSlotDetail {
  id: UUID;
  cst_id: UUID;
  position: number;
  assessment_type: "formative" | "summative";
  anchor_date: ISODate | null;
  status: "scheduled" | "completed" | "skipped";
  exam_status:
    | "not_generated"
    | "PENDING"
    | "IN_FLIGHT"
    | "READY"
    | "ERROR";
  exam_result: unknown;
  exam_paper_html: string | null;
  question_sub_slo_tags: Record<string, UUID> | null;
  exam_tagging_status: "pending" | "done" | "failed" | null;
  exam_error_message: string | null;
  topic_ids: UUID[];
  topic_titles: string[];
}

// ---------------------------------------------------------------------------
// Reteach trigger (dynamic-chapter-planner Phase 3, F-3.1/F-3.2/F-3.3).
//
// A graded formative-assessment slot whose per-sub-SLO mastery is below the
// threshold surfaces a suggestion (GET); the teacher then confirms an explicit
// lightweight | heavy action (POST). Reteach is NEVER auto-applied (D-9). The
// teacher-app badge/confirm UI is not yet built — these typed bindings are the
// ready contract the FE wires onto the FA slot card.
// ---------------------------------------------------------------------------

/** One below-threshold sub-SLO surfaced against a graded FA slot (F-3.1). */
export interface ReteachSuggestionItem {
  sub_slo_id: UUID;
  sub_slo_code: string;
  statement: string;
  mastery_percent: number;
}

/** `GET /api/v2/class-assessment-slots/{id}/reteach-suggestion`. Empty
 * `items` ⇒ no badge. */
export interface ReteachSuggestionResponse {
  class_assessment_slot_id: UUID;
  threshold: number;
  items: ReteachSuggestionItem[];
}

/** Year-end consequence of a reteach INSERT (D-17). Present only when the
 * heavy path had to insert (no downstream flex); null otherwise. */
export interface OverflowConsequence {
  overflow_before: number;
  overflow_after: number;
  newly_overflowed_positions: number[];
  first_overflow_position: number | null;
}

/** `POST /api/v2/class-assessment-slots/{id}/reteach` response. */
export interface ReteachActionResponse {
  class_assessment_slot_id: UUID;
  sub_slo_id: UUID;
  /** 'lightweight' | 'consume_flex' | 'insert' */
  path: "lightweight" | "consume_flex" | "insert";
  /** The reteach lesson slot for the heavy paths; null for lightweight. */
  reteach_slot_id: UUID | null;
  /** Populated only for the 'insert' path. */
  consequence: OverflowConsequence | null;
}

// ---------------------------------------------------------------------------
// Generation (LPs / Exams)
// ---------------------------------------------------------------------------

export type GenerationStatus = "PENDING" | "IN_FLIGHT" | "READY" | "ERROR";

export interface GeneratedLP {
  id: UUID;
  scope: "global" | "class";
  scope_ref_id: UUID | null;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  topic_id: UUID | null;
  lp_type: string;
  status: GenerationStatus;
  job_id: string | null;
  content: string | null;
  content_bilingual: string | null;
  covered_sub_slo_ids: UUID[];
  tagging_status: "pending" | "done" | "failed";
  cost_usd: number | null;
  error_message: string | null;
}

export interface GeneratedExam {
  id: UUID;
  scope: "global" | "class";
  scope_ref_id: UUID | null;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  topic_ids_hash: string;
  generation_type: string;
  status: GenerationStatus;
  job_id: string | null;
  result: unknown;             // exam JSON tree; consumer narrows
  exam_paper_html: string | null;
  question_sub_slo_tags: Record<string, UUID> | null;
  tagging_status: "pending" | "done" | "failed";
  cost_usd: number | null;
  error_message: string | null;
}

export interface GenerationStatusBucket {
  total: number;
  pending: number;
  in_flight: number;
  ready: number;
  error: number;
}

export interface BreakdownGenerationStatus {
  lp: GenerationStatusBucket;
  exam: GenerationStatusBucket;
}

// ---------------------------------------------------------------------------
// Today / Calendar
// ---------------------------------------------------------------------------

export interface LessonSlotEntry {
  slot_id: UUID;
  position: number;
  slot_type: "lesson" | "revision";
  lp_type: string | null;
  topic_id: UUID | null;
  topic_title: string | null;
  status: string;
  anchor_date: ISODate | null;
}

export interface AssessmentSlotEntry {
  slot_id: UUID;
  position: number;
  assessment_type: "formative" | "summative";
  status: string;
  anchor_date: ISODate | null;
  topic_ids: UUID[];
}

export interface PreviousTaughtSummary {
  slot_id: UUID;
  position: number;
  topic_id: UUID | null;
  taught_on: ISODate | null;
}

/** The next lesson slot after today's position (by global position). */
export interface NextUpSummary {
  slot_id: UUID;
  position: number;
  topic_id: UUID | null;
  lp_type: string | null;
  projected_date: ISODate | null;
}

/** The chapter the class is currently on (first non-done chapter in the
 * org-breakdown / class path order). Set whenever a path exists. */
export interface CurrentChapterSummary {
  book_chapter_id: UUID;
  chapter_number: number | null;
  title: string | null;
  status: string; // 'yet_to_start' | 'in_progress' | 'done'
}

export interface TodayEntry {
  cst_id: UUID;
  subject_id: UUID;
  subject_code: string;
  grade_id: UUID;
  grade_code: number;
  day_number: number | null;
  current_chapter: CurrentChapterSummary | null;
  lesson_slot: LessonSlotEntry | null;
  assessment_slot: AssessmentSlotEntry | null;
  previous_taught: PreviousTaughtSummary | null;
  next_up: NextUpSummary | null;
  is_conflict: boolean;
  is_overflow: boolean;
}

export interface TodayResponse {
  items: TodayEntry[];
  as_of: ISODate;
}

export interface CalendarDay {
  day: ISODate;
  lesson_slots: LessonSlotEntry[];
  assessment_slots: AssessmentSlotEntry[];
}

export interface CalendarCSTSchedule {
  cst_id: UUID;
  subject_id: UUID;
  subject_code: string;
  grade_id: UUID;
  grade_code: number;
  days: CalendarDay[];
}

export interface CalendarResponse {
  week_start: ISODate;
  week_end: ISODate;
  csts: CalendarCSTSchedule[];
}

// ---------------------------------------------------------------------------
// Coverage / progress
// ---------------------------------------------------------------------------

export type SubSLOCoverageStatus = "taught" | "not_taught" | "unknown";

export interface SubSLOCoverageEntry {
  sub_slo_id: UUID;
  sub_slo_code: string;
  status: SubSLOCoverageStatus;
}

export interface SubSLOCoverageResponse {
  cst_id: UUID;
  joined_at_position: number;
  items: SubSLOCoverageEntry[];
}

// ---------------------------------------------------------------------------
// Holidays
// ---------------------------------------------------------------------------

/**
 * One row in the union of org / school / cst holiday sources.
 * `action` is set only on school/cst overrides; org holidays always add.
 */
export interface Holiday {
  date: ISODate;
  name: string | null;
  source: "org" | "school" | "cst";
  action: "add" | "remove" | null;
}

export interface HolidayListResponse {
  items: Holiday[];
  effective_dates: ISODate[];
}

export interface HolidayCreated {
  id: UUID;
  date: ISODate;
}

// ---------------------------------------------------------------------------
// Usage
// ---------------------------------------------------------------------------

export interface UsageBySubject {
  subject_code: string;
  lp_count: number;
  exam_count: number;
  cost_usd: number;
}

export interface UsageByCurriculum {
  curriculum_code: string;
  lp_count: number;
  exam_count: number;
  cost_usd: number;
}

export interface UsageReport {
  lp_count: number;
  exam_count: number;
  total_cost_usd: number;
  by_subject: UsageBySubject[];
  by_curriculum: UsageByCurriculum[];
  start: ISODate | null;
  end: ISODate | null;
}

// ---------------------------------------------------------------------------
// Action responses
// ---------------------------------------------------------------------------

export interface MarkActionResponse {
  slot_id: UUID;
  status: string;
  occurred_on: ISODate;
}

export interface OnboardResponse {
  cst_id: UUID;
  joined_at_position: number;
  current_sequence_position: number;
}

// ---------------------------------------------------------------------------
// Core fetch wrapper
// ---------------------------------------------------------------------------

const API_KEY_STORAGE_KEY = "dars_org_api_key";
const ADMIN_SESSION_STORAGE_KEY = "dars_admin_session";

export class DarsApiError extends Error {
  constructor(
    public status: number,
    public detail: unknown,
    public url: string,
  ) {
    super(
      `Dars API ${status} on ${url}: ${
        typeof detail === "string" ? detail : JSON.stringify(detail)
      }`,
    );
    this.name = "DarsApiError";
  }
}

function getBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error(
      "NEXT_PUBLIC_API_URL is not configured — set it in webapp/.env.local " +
        "or the Railway env vars (e.g. https://dars-staging.up.railway.app).",
    );
  }
  return url.replace(/\/$/, "");
}

export function getApiKey(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(API_KEY_STORAGE_KEY) ?? "";
}

export function setApiKey(key: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

export function clearApiKey(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(API_KEY_STORAGE_KEY);
}

export function getAdminSession(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(ADMIN_SESSION_STORAGE_KEY) ?? "";
}

export function setAdminSession(token: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ADMIN_SESSION_STORAGE_KEY, token);
}

export function clearAdminSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ADMIN_SESSION_STORAGE_KEY);
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  /**
   * - "org" (default): send X-API-Key. Used by the teacher app.
   * - "admin": send X-Admin-Session. Used by the dashboard.
   * - "none": send no auth. Used by signup/login.
   */
  auth?: "org" | "admin" | "none";
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", query, body, auth = "org" } = opts;
  const base = getBaseUrl();

  let url = base + path;
  if (query) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null) sp.set(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += `?${qs}`;
  }

  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (auth === "org") {
    const key = getApiKey();
    if (key) {
      headers["X-API-Key"] = key;
    } else {
      // Fall through to admin session — server-side get_current_org
      // accepts either header. Dashboard pages typically don't have an
      // org API key (only the prefix is visible after signup), so they
      // implicitly use the admin session for read endpoints.
      const session = getAdminSession();
      if (!session) {
        throw new DarsApiError(
          401,
          "missing api key — set localStorage.dars_org_api_key or log in via /dashboard",
          url,
        );
      }
      headers["X-Admin-Session"] = session;
    }
  } else if (auth === "admin") {
    const session = getAdminSession();
    if (!session) {
      throw new DarsApiError(
        401,
        "missing admin session — log in via /dashboard/login",
        url,
      );
    }
    headers["X-Admin-Session"] = session;
  }

  const res = await fetch(url, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      detail = await res.json();
    } catch {
      // body wasn't JSON; keep statusText
    }
    throw new DarsApiError(res.status, detail, url);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Tenancy (`/api/v2/*`)
// ---------------------------------------------------------------------------

export const tenancy = {
  getMyOrg: () => request<Org>("/api/v2/orgs/me"),

  getSchools: () => request<ListResponse<School>>("/api/v2/schools"),
  getSchool: (id: UUID) => request<School>(`/api/v2/schools/${id}`),

  getTeachers: (school_id?: UUID) =>
    request<ListResponse<Teacher>>("/api/v2/teachers", { query: { school_id } }),
  getTeacher: (id: UUID) => request<Teacher>(`/api/v2/teachers/${id}`),

  getAcademicYears: (school_id?: UUID) =>
    request<ListResponse<AcademicYear>>("/api/v2/academic-years", {
      query: { school_id },
    }),
  getAcademicYear: (id: UUID) => request<AcademicYear>(`/api/v2/academic-years/${id}`),

  getClasses: (params: { school_id?: UUID; academic_year_id?: UUID } = {}) =>
    request<ListResponse<SchoolClass>>("/api/v2/classes", { query: params }),
  getClass: (id: UUID) => request<SchoolClass>(`/api/v2/classes/${id}`),

  getCSTs: (params: { teacher_id?: UUID; school_class_id?: UUID } = {}) =>
    request<ListResponse<CST>>("/api/v2/csts", { query: params }),
  getCST: (id: UUID) => request<CST>(`/api/v2/csts/${id}`),
};

// ---------------------------------------------------------------------------
// Curriculum (`/api/v2/*`)
// ---------------------------------------------------------------------------

export const curriculum = {
  getCurriculums: () => request<ListResponse<Curriculum>>("/api/v2/curriculums"),
  getCurriculum: (id: UUID) => request<Curriculum>(`/api/v2/curriculums/${id}`),

  getGrades: () => request<ListResponse<Grade>>("/api/v2/grades"),
  getSubjects: () => request<ListResponse<Subject>>("/api/v2/subjects"),

  getSLOs: (params: {
    curriculum_id?: UUID;
    grade_id?: UUID;
    subject_id?: UUID;
  } = {}) => request<ListResponse<SLO>>("/api/v2/slos", { query: params }),
  getSLO: (id: UUID) => request<SLO>(`/api/v2/slos/${id}`),

  getSubSLOs: (slo_id: UUID) =>
    request<ListResponse<SubSLO>>("/api/v2/sub-slos", { query: { slo_id } }),
  getSubSLO: (id: UUID) => request<SubSLO>(`/api/v2/sub-slos/${id}`),
};

// ---------------------------------------------------------------------------
// Books (`/api/v2/*`)
// ---------------------------------------------------------------------------

export const books = {
  getBooks: (params: { curriculum_id?: UUID; grade_id?: UUID; subject_id?: UUID } = {}) =>
    request<ListResponse<Book>>("/api/v2/books", { query: params }),
  getBook: (id: UUID) => request<Book>(`/api/v2/books/${id}`),
  /** Full nested tree: book + chapters (+slos, chapter_text) + topics (+sub_slos). */
  getBookTree: (id: UUID) => request<BookTree>(`/api/v2/books/${id}/tree`),

  getBookChapters: (book_id: UUID) =>
    request<ListResponse<BookChapter>>("/api/v2/book-chapters", {
      query: { book_id },
    }),
  getBookChapter: (id: UUID) => request<BookChapter>(`/api/v2/book-chapters/${id}`),

  getTopics: (book_chapter_id: UUID) =>
    request<ListResponse<Topic>>("/api/v2/topics", { query: { book_chapter_id } }),
  getTopic: (id: UUID) => request<Topic>(`/api/v2/topics/${id}`),

  getTopicSubSLOs: (topic_id: UUID) =>
    request<ListResponse<SubSLO>>(`/api/v2/topics/${topic_id}/sub-slos`),
};

// ---------------------------------------------------------------------------
// Core Book Import (`/api/v2/admin/*`) — admin-only, mirrors router_book_import.py
// ---------------------------------------------------------------------------

/** An importable book from taleemabad-core (fde_staging). */
export interface CoreBook {
  core_book_id: number;
  title: string;
  publisher: string | null;
  edition: string | null;
  published_year: number | null;
  total_chapters: number | null;
  grade: string | null;
  subject: string | null;
  status: string;
  already_imported: boolean;
}

export type ImportRunStatus = "pending" | "running" | "succeeded" | "failed";

/** A single import execution (the `import_runs` row). */
export interface ImportRun {
  id: UUID;
  core_book_id: number;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  dars_book_id: UUID | null;
  status: ImportRunStatus;
  current_step: string | null;
  /** per-step state: { slos: {status, count}, sub_slos: {...}, ... } */
  steps: Record<string, { status?: string; count?: number; [k: string]: unknown }>;
  /** final row counts: { slos, sub_slos, chapters, topics, topic_sub_slos, book_chapter_slos } */
  counts: Record<string, number>;
  warnings: string[];
  error: string | null;
  started_by: string | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

/** Ordered list of the steps the importer reports, for rendering the checklist. */
export const IMPORT_STEPS = [
  "slos",
  "sub_slos",
  "book_chapters",
  "topics",
  "mappings",
] as const;

export const bookImport = {
  /**
   * Look up importable taleemabad-core books. Pass `book_id` for an exact match
   * or `search` for a title filter; `schema` selects the source DB schema
   * (default fde_staging). 503 if core DB not configured.
   */
  getCoreBooks: (params: { search?: string; book_id?: number; schema?: string } = {}) =>
    request<ListResponse<CoreBook>>("/api/v2/admin/core-books", {
      query: {
        search: params.search,
        book_id: params.book_id,
        schema: params.schema,
      },
      auth: "admin",
    }),
  /** Kick off an import → 202 { import_run_id }. 409 if one is already running. */
  start: (body: { core_book_id: number; curriculum_id?: UUID; schema_name?: string }) =>
    request<{ import_run_id: UUID }>("/api/v2/admin/book-imports", {
      method: "POST", body, auth: "admin",
    }),
  getRun: (id: UUID) =>
    request<ImportRun>(`/api/v2/admin/book-imports/${id}`, { auth: "admin" }),
  getRuns: () =>
    request<ListResponse<ImportRun>>("/api/v2/admin/book-imports", { auth: "admin" }),
};

// ---------------------------------------------------------------------------
// Syllabus breakdowns (`/api/v2/syllabus-breakdowns/*`)
// ---------------------------------------------------------------------------

export interface SyllabusChapter {
  id: UUID;
  syllabus_breakdown_id: UUID;
  book_chapter_id: UUID;
  position: number;
  /** Chapter explicit date range. Null until set. */
  start_date: ISODate | null;
  end_date: ISODate | null;
  /** Teaching days derived from the range vs. the academic calendar; null when no range. */
  derived_teaching_days: number | null;
}

/** Advisory, non-blocking chapter date-range warning. */
export interface ChapterRangeWarning {
  type: "overlap" | "gap" | "zero_teaching_days";
  chapter_ids: UUID[];
}

/**
 * A reserved non-teaching date range on a breakdown: an exam period or a
 * general holiday (Eid, public holidays). Both share this shape (D-1/D-14).
 */
export interface BreakdownDateRange {
  id: UUID;
  syllabus_breakdown_id: UUID;
  start_date: ISODate;
  end_date: ISODate;
  name: string;
  created_at: ISODateTime;
}

export interface SyllabusBreakdownDetail extends SyllabusBreakdown {
  chapters: SyllabusChapter[];
  chapter_range_warnings: ChapterRangeWarning[];
  /** Reserved exam date ranges (excluded from teaching days). */
  exam_periods: BreakdownDateRange[];
  /** General holiday ranges (Eid etc.) that inherit into class plans. */
  holidays: BreakdownDateRange[];
}

export const syllabusBreakdowns = {
  getBreakdowns: (params: { status?: string } = {}) =>
    request<ListResponse<SyllabusBreakdown>>("/api/v2/syllabus-breakdowns", {
      query: params,
    }),

  /** Single breakdown read returns chapters hydrated. */
  getBreakdown: (id: UUID) =>
    request<SyllabusBreakdownDetail>(`/api/v2/syllabus-breakdowns/${id}`),

  create: (body: {
    curriculum_id: UUID;
    grade_id: UUID;
    subject_id: UUID;
    book_id?: UUID | null;
  }) =>
    request<SyllabusBreakdown>("/api/v2/syllabus-breakdowns", {
      method: "POST",
      body,
    }),

  update: (id: UUID, body: { book_id?: UUID | null }) =>
    request<SyllabusBreakdown>(`/api/v2/syllabus-breakdowns/${id}`, {
      method: "PATCH",
      body,
    }),

  publish: (id: UUID) =>
    request<SyllabusBreakdown>(`/api/v2/syllabus-breakdowns/${id}/publish`, {
      method: "POST",
    }),

  delete: (id: UUID) =>
    request<void>(`/api/v2/syllabus-breakdowns/${id}`, { method: "DELETE" }),

  patchChapter: (
    breakdownId: UUID,
    chapterId: UUID,
    body: { position?: number; start_date?: ISODate; end_date?: ISODate },
  ) =>
    request<SyllabusChapter>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/chapters/${chapterId}`,
      { method: "PATCH", body },
    ),

  addChapter: (
    breakdownId: UUID,
    body: { book_chapter_id: UUID; position: number; start_date?: ISODate; end_date?: ISODate },
  ) =>
    request<SyllabusChapter>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/chapters`,
      { method: "POST", body },
    ),

  deleteChapter: (breakdownId: UUID, chapterId: UUID) =>
    request<void>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/chapters/${chapterId}`,
      { method: "DELETE" },
    ),

  // --- Exam periods (reserved non-teaching ranges, D-1) ---
  addExamPeriod: (
    breakdownId: UUID,
    body: { start_date: ISODate; end_date: ISODate; name: string },
  ) =>
    request<BreakdownDateRange>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/exam-periods`,
      { method: "POST", body },
    ),

  updateExamPeriod: (
    breakdownId: UUID,
    examPeriodId: UUID,
    body: { start_date?: ISODate; end_date?: ISODate; name?: string },
  ) =>
    request<BreakdownDateRange>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/exam-periods/${examPeriodId}`,
      { method: "PATCH", body },
    ),

  deleteExamPeriod: (breakdownId: UUID, examPeriodId: UUID) =>
    request<void>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/exam-periods/${examPeriodId}`,
      { method: "DELETE" },
    ),

  // --- Breakdown holidays (Eid etc., inherit into class plans, D-14) ---
  addHoliday: (
    breakdownId: UUID,
    body: { start_date: ISODate; end_date: ISODate; name: string },
  ) =>
    request<BreakdownDateRange>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/holidays`,
      { method: "POST", body },
    ),

  updateHoliday: (
    breakdownId: UUID,
    holidayId: UUID,
    body: { start_date?: ISODate; end_date?: ISODate; name?: string },
  ) =>
    request<BreakdownDateRange>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/holidays/${holidayId}`,
      { method: "PATCH", body },
    ),

  deleteHoliday: (breakdownId: UUID, holidayId: UUID) =>
    request<void>(
      `/api/v2/syllabus-breakdowns/${breakdownId}/holidays/${holidayId}`,
      { method: "DELETE" },
    ),
};

// ---------------------------------------------------------------------------
// Class slots + actions (`/api/v2/*` for actions, `/api/v1/*` for detail)
// ---------------------------------------------------------------------------

export const slots = {
  /** F3.13 — full slot detail with LP status + content. */
  getLessonSlotDetail: (slot_id: UUID) =>
    request<ClassLessonSlotDetail>(`/api/v1/class-lesson-slots/${slot_id}`),

  /**
   * On-demand per-slot LP generation. Looks up the global LP cache and
   * returns the existing row when one exists (READY/PENDING/IN_FLIGHT),
   * re-requests on ERROR, else dispatches a fresh generation and links the
   * slot. Idempotent — safe to re-call. Poll getLessonSlotDetail() for the
   * `lp_status` until READY/ERROR.
   */
  generateLPForSlot: (slot_id: UUID) =>
    request<GenerateLPResponse>(
      `/api/v1/class-lesson-slots/${slot_id}/generate-lp`,
      { method: "POST" },
    ),

  /**
   * F-3.3 — On-demand per-slot FA exam generation. The assessment-slot
   * analogue of generateLPForSlot: looks up the global exam cache (keyed on
   * curriculum + covered topics + generation_type + config hash) and returns
   * the existing row when one exists (READY/PENDING/IN_FLIGHT), re-requests on
   * ERROR, else dispatches a fresh generation and links the slot. Idempotent —
   * safe to re-call. Poll getAssessmentSlotDetail() for `exam_status` until
   * READY/ERROR.
   */
  generateExamForSlot: (slot_id: UUID) =>
    request<GenerateExamResponse>(
      `/api/v1/class-assessment-slots/${slot_id}/generate-exam`,
      { method: "POST" },
    ),

  /**
   * dynamic-chapter-planner F-3.1 — the below-threshold sub-SLOs for a graded
   * FA slot (the teacher-app reteach-badge payload). Read only; empty `items`
   * ⇒ no badge. Acting on a suggestion requires the explicit confirmReteach
   * POST below — reteach NEVER auto-applies (D-9).
   */
  getReteachSuggestion: (slot_id: UUID) =>
    request<ReteachSuggestionResponse>(
      `/api/v2/class-assessment-slots/${slot_id}/reteach-suggestion`,
    ),

  /**
   * dynamic-chapter-planner F-3.2/F-3.3 — apply a teacher-confirmed reteach for
   * one sub-SLO. `mode` is the explicit teacher choice (no auto-apply, D-9):
   *   'lightweight' (default) — flip coverage to needs-rework; no slot, no shift.
   *   'heavy' — consume the nearest downstream flex slot (no shift), else insert
   *     a new lesson slot (shifts the tail) and return the overflow consequence
   *     (which tail slot, if any, is pushed past year-end — D-17). The reteach
   *     slot gets a revision LP on the on-demand path (D-10).
   */
  confirmReteach: (
    slot_id: UUID,
    body: { sub_slo_id: UUID; mode?: "lightweight" | "heavy" },
  ) =>
    request<ReteachActionResponse>(
      `/api/v2/class-assessment-slots/${slot_id}/reteach`,
      { method: "POST", body },
    ),

  /** F4.6 — all lesson slots for a CST, joined with breakdown chapter + LP status. */
  listLessonSlotsForCST: (cst_id: UUID) =>
    request<ClassLessonSlotListResponse>(
      `/api/v2/csts/${cst_id}/lesson-slots`,
    ),

  /** F4.7 — all assessment slots for a CST. */
  listAssessmentSlotsForCST: (cst_id: UUID) =>
    request<ClassAssessmentSlotListResponse>(
      `/api/v2/csts/${cst_id}/assessment-slots`,
    ),

  /**
   * class-timeline-view — lessons + assessments interleaved by position,
   * each stamped with the projector's date + conflict/overflow flags.
   */
  getTimeline: (cst_id: UUID) =>
    request<CstTimelineResponse>(`/api/v2/csts/${cst_id}/timeline`),

  /** F4.13 — single assessment slot detail including exam_result JSON. */
  getAssessmentSlotDetail: (slot_id: UUID) =>
    request<ClassAssessmentSlotDetail>(
      `/api/v1/class-assessment-slots/${slot_id}`,
    ),

  markTaught: (slot_id: UUID, body: { taught_on: ISODate; notes?: string }) =>
    request<MarkActionResponse>(
      `/api/v2/class-lesson-slots/${slot_id}/mark-taught`,
      { method: "POST", body },
    ),

  skipLesson: (slot_id: UUID, body: { occurred_on: ISODate; reason?: string }) =>
    request<MarkActionResponse>(`/api/v2/class-lesson-slots/${slot_id}/skip`, {
      method: "POST",
      body,
    }),

  completeAssessment: (
    slot_id: UUID,
    body: { taught_on: ISODate; notes?: string },
  ) =>
    request<MarkActionResponse>(
      `/api/v2/class-assessment-slots/${slot_id}/complete`,
      { method: "POST", body },
    ),

  skipAssessment: (slot_id: UUID, body: { occurred_on: ISODate; reason?: string }) =>
    request<MarkActionResponse>(
      `/api/v2/class-assessment-slots/${slot_id}/skip`,
      { method: "POST", body },
    ),

  /**
   * teacher-readonly-syllabus — the class teaching path (read-only): the
   * org-decided chapters (ordered by `position`), each with its date range,
   * derived slot count + status. Auto-seeded on first read (Phase 1). The
   * teacher cannot mutate the path; the only action is generating a plan.
   */
  getSyllabus: (cst_id: UUID) =>
    request<SyllabusForCstResponse>(`/api/v2/csts/${cst_id}/syllabus`),

  /** "Break it down" (Action 2): generate a path chapter's Chapter Plan into
   * the class slots, sized by the teacher's timetable. 422 if no dates / not
   * in path / already broken down. */
  breakDownChapter: (cst_id: UUID, book_chapter_id: UUID) =>
    request<GenerateChapterPlanResponse>(
      `/api/v2/csts/${cst_id}/chapters/${book_chapter_id}/plan`,
      { method: "POST" },
    ),
};

/**
 * teacher-readonly-syllabus — a chapter in the CLASS PATH (the org-decided
 * chapters, ordered by `position`). Status is derived from the chapter's
 * generated slots (D-4): `done` = all terminal, `in_progress` = some
 * terminal, `yet_to_start` = none terminal (incl. not-yet-broken-down).
 */
export type ClassPathChapterStatus = "yet_to_start" | "in_progress" | "done";

export interface ClassPathChapter {
  book_chapter_id: UUID;
  chapter_number: number;
  title: string;
  position: number;
  start_date: ISODate | null;
  end_date: ISODate | null;
  /** Capacity: teaching periods in the date range (non-zero once dated). NOT "generated". */
  slot_count: number;
  /** True once the chapter has actually been broken down (has generated slots). */
  is_generated: boolean;
  status: ClassPathChapterStatus;
}

export interface SyllabusForCstResponse {
  cst_id: UUID;
  syllabus_breakdown_id: UUID | null;
  periods_per_week: number;
  /**
   * The class teaching path, ordered by `position` — NOT the global book.
   * Empty array = the school hasn't published a syllabus for this class yet.
   */
  chapters: ClassPathChapter[];
}

export interface GenerateChapterPlanResponse {
  cst_id: UUID;
  book_chapter_id: UUID;
  slot_count: number;
  lesson_slot_count: number;
  assessment_slot_count: number;
  warnings: string[];
}

// ---------------------------------------------------------------------------
// Generations (`/api/v1/*`)
// ---------------------------------------------------------------------------

export const generations = {
  /**
   * The backend has no GET /generated-lps/{id} yet — the LP body is delivered
   * via slots.getLessonSlotDetail() which joins the row. This stays as a
   * placeholder so callers know where it'll live once it ships.
   */
  getGeneratedLP: async (_id: UUID): Promise<GeneratedLP> => {
    throw new Error(
      "generations.getGeneratedLP not wired yet — read via slots.getLessonSlotDetail() for now.",
    );
  },

  getGeneratedExam: async (_id: UUID): Promise<GeneratedExam> => {
    throw new Error(
      "generations.getGeneratedExam not wired yet — backend GET endpoint pending.",
    );
  },

  refreshLP: (id: UUID) =>
    request<{ ok: boolean; status: string; action: string }>(
      `/api/v1/generated-lps/${id}/refresh`,
      { method: "POST" },
    ),

  refreshExam: (id: UUID) =>
    request<{ ok: boolean; status: string; action: string }>(
      `/api/v1/generated-exams/${id}/refresh`,
      { method: "POST" },
    ),

  getBreakdownGenerationStatus: (breakdown_id: UUID) =>
    request<BreakdownGenerationStatus>(
      `/api/v1/breakdowns/${breakdown_id}/generation-status`,
    ),
};

// ---------------------------------------------------------------------------
// Today / Calendar (`/api/v2/*`)
// ---------------------------------------------------------------------------

export const today = {
  get: () => request<TodayResponse>("/api/v2/today"),
};

export const calendar = {
  /** week_start: a Monday in ISO date format. Required by the server (no default). */
  get: (week_start: ISODate) =>
    request<CalendarResponse>("/api/v2/me/calendar", { query: { week_start } }),
};

// ---------------------------------------------------------------------------
// Coverage / onboarding (`/api/v2/*`)
// ---------------------------------------------------------------------------

export const progress = {
  getSubSLOCoverage: (cst_id: UUID) =>
    request<SubSLOCoverageResponse>(`/api/v2/csts/${cst_id}/sub-slo-coverage`),
};

export const onboarding = {
  onboardCST: (
    cst_id: UUID,
    body: { chapter_position: number; chapter_day: number },
  ) =>
    request<OnboardResponse>(`/api/v2/csts/${cst_id}/onboard`, {
      method: "POST",
      body,
    }),
};

// ---------------------------------------------------------------------------
// Holidays (`/api/v2/*`)
// ---------------------------------------------------------------------------

export const holidays = {
  getOrgHolidays: (org_id: UUID) =>
    request<HolidayListResponse>(`/api/v2/orgs/${org_id}/holidays`),
  getSchoolHolidays: (school_id: UUID) =>
    request<HolidayListResponse>(`/api/v2/schools/${school_id}/holidays`),
  getCSTHolidays: (cst_id: UUID) =>
    request<HolidayListResponse>(`/api/v2/csts/${cst_id}/holidays`),

  addCSTOverride: (
    cst_id: UUID,
    body: { date: ISODate; name?: string; action: "add" | "remove" },
  ) =>
    request<HolidayCreated>(`/api/v2/csts/${cst_id}/holiday-overrides`, {
      method: "POST",
      body,
    }),
};

// ---------------------------------------------------------------------------
// Usage (`/api/v1/*`)
// ---------------------------------------------------------------------------

export const usage = {
  getOrgUsage: (params: { start?: ISODate; end?: ISODate } = {}) =>
    request<UsageReport>("/api/v1/orgs/me/usage", { query: params }),
};

// ---------------------------------------------------------------------------
// Mastery (F4.13 backend pending)
// ---------------------------------------------------------------------------

export interface SubmitExamResultsBody {
  students_present: number;
  per_question: { question_index: number; students_correct: number; marks_total?: number }[];
  assessed_on?: ISODate;
  recorded_by_teacher_id?: UUID;
}

export interface SubmitResultsResponse {
  exam_result_id: UUID;
  sub_slo_mastery_rows: number;
}

export const mastery = {
  submitExamResults: (slot_id: UUID, body: SubmitExamResultsBody) =>
    request<SubmitResultsResponse>(
      `/api/v1/class-assessment-slots/${slot_id}/results`,
      { method: "POST", body },
    ),
};

// ---------------------------------------------------------------------------
// Quick generation (F4.14 backend pending)
// ---------------------------------------------------------------------------

export interface QuickLPBody {
  grade: number;
  subject: string;
  page_number: string;       // "5" or "5-7"
  lp_type: string;
  generate_bilingual?: boolean;
}

export interface QuickExamBody {
  grade: number;
  subject: string;
  page_ranges: string;       // "5" or "5-7" or "1, 3, 5-7"
  generation_type?: "exam" | "class_assessment";
  question_types?: ("seen" | "unseen")[];
  unseen_categories?: ("objective" | "subjective")[];
  unseen_objective_types?: string[];
  unseen_subjective_types?: string[];
  unseen_objective_counts?: Record<string, number>;
  unseen_subjective_counts?: Record<string, number>;
  long_question_sub_types?: string[];
  include_answer_key?: boolean;
}

/** Returned by the quick endpoints: the new row id + initial status. */
export interface QuickGenerationCreated {
  id: UUID;
  status: GenerationStatus;
  job_id: string | null;
}

export const quick = {
  lp: (body: QuickLPBody) =>
    request<QuickGenerationCreated>("/api/v1/quick-lp", {
      method: "POST",
      body,
    }),
  exam: (body: QuickExamBody) =>
    request<QuickGenerationCreated>("/api/v1/quick-exam", {
      method: "POST",
      body,
    }),
};

// ---------------------------------------------------------------------------
// Admin auth + tenancy CRUD (F5)
// ---------------------------------------------------------------------------

export interface AdminSignupBody {
  email: string;
  password: string;
  name: string;
  org_name: string;
  curriculum_code: string;
}

export interface AdminSignupResponse {
  session_token: UUID;
  expires_at: string;
  org_id: UUID;
  org_name: string;
  admin_id: UUID;
  api_key: string;
  api_key_prefix: string;
}

export interface AdminLoginBody {
  email: string;
  password: string;
}

export interface AdminLoginResponse {
  session_token: UUID;
  expires_at: string;
  admin_id: UUID;
  org_id: UUID;
}

export interface AdminMeResponse {
  admin_id: UUID;
  org_id: UUID;
  org_name: string;
  email: string;
  name: string;
  curriculum_id: UUID;
  curriculum_code: string;
  default_teacher_id: UUID | null;
  api_key_prefix: string;
}

export interface RotateKeyResponse {
  api_key: string;
  api_key_prefix: string;
}

export const admin = {
  signup: (body: AdminSignupBody) =>
    request<AdminSignupResponse>("/api/v1/admin/signup", {
      method: "POST", body, auth: "none",
    }),
  login: (body: AdminLoginBody) =>
    request<AdminLoginResponse>("/api/v1/admin/login", {
      method: "POST", body, auth: "none",
    }),
  logout: () =>
    request<void>("/api/v1/admin/logout", { method: "POST", auth: "admin" }),
  me: () => request<AdminMeResponse>("/api/v1/admin/me", { auth: "admin" }),

  patchOrg: (body: { name?: string; default_teacher_id?: UUID }) =>
    request<AdminMeResponse>("/api/v1/orgs/me", {
      method: "PATCH", body, auth: "admin",
    }),
  rotateApiKey: () =>
    request<RotateKeyResponse>("/api/v1/orgs/me/rotate-api-key", {
      method: "POST", auth: "admin",
    }),

  // Tenancy CRUD
  createSchool: (body: { name: string }) =>
    request<School>("/api/v1/schools", {
      method: "POST", body, auth: "admin",
    }),
  updateSchool: (id: UUID, body: { name: string }) =>
    request<School>(`/api/v1/schools/${id}`, {
      method: "PATCH", body, auth: "admin",
    }),

  createTeacher: (body: { school_id: UUID; name: string; email?: string }) =>
    request<Teacher>("/api/v1/teachers", {
      method: "POST", body, auth: "admin",
    }),
  updateTeacher: (id: UUID, body: { name?: string; email?: string }) =>
    request<Teacher>(`/api/v1/teachers/${id}`, {
      method: "PATCH", body, auth: "admin",
    }),

  createAcademicYear: (body: {
    school_id: UUID;
    name: string;
    start_date: ISODate;
    end_date: ISODate;
  }) =>
    request<AcademicYear>("/api/v1/academic-years", {
      method: "POST", body, auth: "admin",
    }),
  updateAcademicYear: (id: UUID, body: { name?: string; start_date?: ISODate; end_date?: ISODate }) =>
    request<AcademicYear>(`/api/v1/academic-years/${id}`, {
      method: "PATCH", body, auth: "admin",
    }),

  // Accepts either X-Admin-Session (dashboard) or X-API-Key (teacher app /
  // B2B integrator) — server's get_current_org resolves either to an org.
  createClass: (body: {
    school_id: UUID;
    academic_year_id: UUID;
    grade_id: UUID;
    section: string;
    name?: string;
  }) =>
    request<SchoolClass>("/api/v1/classes", {
      method: "POST", body, auth: "org",
    }),

  createCST: (body: {
    school_class_id: UUID;
    subject_id: UUID;
    teacher_id: UUID;
    book_id?: UUID;
  }) =>
    request<CST>("/api/v1/csts", {
      method: "POST", body, auth: "org",
    }),
  updateCST: (id: UUID, body: { teacher_id?: UUID; book_id?: UUID }) =>
    request<CST>(`/api/v1/csts/${id}`, {
      method: "PATCH", body, auth: "admin",
    }),
};

// ---------------------------------------------------------------------------
// Admin: generations (failures + retry) + coverage summary
// ---------------------------------------------------------------------------

export interface FailureLPListItem {
  id: UUID;
  cache_key: string | null;
  scope: string;
  scope_ref_id: UUID | null;
  topic_id: UUID | null;
  lp_type: string | null;
  error_message: string | null;
  created_at: string;
}

export interface FailureExamListItem {
  id: UUID;
  cache_key: string | null;
  scope: string;
  scope_ref_id: UUID | null;
  generation_type: string | null;
  error_message: string | null;
  created_at: string;
}

export interface FailureListResponse {
  lps: FailureLPListItem[];
  exams: FailureExamListItem[];
}

export interface RetryResponse {
  id: UUID;
  status: GenerationStatus;
  job_id: string | null;
}

export interface SLOCoverageBucket {
  slo_id: UUID;
  slo_code: string;
  slo_statement: string;
  sub_slo_count: number;
  taught_count: number;
  avg_mastery_percent: number | null;
}

export interface SLOCoverageSummaryResponse {
  items: SLOCoverageBucket[];
}

export const adminGenerations = {
  listFailures: () =>
    request<FailureListResponse>("/api/v1/orgs/me/generation-failures"),
  retryLP: (id: UUID) =>
    request<RetryResponse>(`/api/v1/generated-lps/${id}/retry`, { method: "POST" }),
  retryExam: (id: UUID) =>
    request<RetryResponse>(`/api/v1/generated-exams/${id}/retry`, { method: "POST" }),
  getCoverageSummary: (params: { grade_id?: UUID; subject_id?: UUID } = {}) =>
    request<SLOCoverageSummaryResponse>("/api/v1/orgs/me/coverage-summary", {
      query: params,
    }),
};

// ---------------------------------------------------------------------------
// Holidays — admin POST endpoints already supported by router_holidays.py
// (path: POST /api/v2/orgs/{org_id}/holidays, schools/{id}/holiday-overrides)
// ---------------------------------------------------------------------------

export const adminHolidays = {
  addOrgHoliday: (org_id: UUID, body: {
    academic_year_id: UUID;
    date: ISODate;
    name: string;
  }) =>
    request<HolidayCreated>(`/api/v2/orgs/${org_id}/holidays`, {
      method: "POST", body,
    }),
  addSchoolOverride: (school_id: UUID, body: {
    date: ISODate;
    name?: string;
    action: "add" | "remove";
  }) =>
    request<HolidayCreated>(`/api/v2/schools/${school_id}/holiday-overrides`, {
      method: "POST", body,
    }),
};

// ---------------------------------------------------------------------------
// Default export bundles every namespace for ergonomic imports
// ---------------------------------------------------------------------------

export const darsApi = {
  tenancy,
  curriculum,
  books,
  syllabusBreakdowns,
  slots,
  generations,
  today,
  calendar,
  progress,
  onboarding,
  holidays,
  usage,
  mastery,
  quick,
  admin,
  adminGenerations,
  adminHolidays,
  // utilities
  getApiKey,
  setApiKey,
  clearApiKey,
  getAdminSession,
  setAdminSession,
  clearAdminSession,
};

export default darsApi;
