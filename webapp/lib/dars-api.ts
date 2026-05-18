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
  code: string;        // 'G1'..'G5'
  label: string;
  grade_order: number;
}

export interface Subject {
  id: UUID;
  code: string;        // 'Eng' | 'Urdu' | 'Maths' | 'Science' | 'GK'
  name: string;
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
}

/**
 * `chapter_text` is a structured page slice — list of objects keyed by
 * page-content type ({ kind, text } pairs etc). It's only populated when
 * the request hits `?include=chapter_text`; otherwise null.
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

// ---------------------------------------------------------------------------
// Breakdowns + slots
// ---------------------------------------------------------------------------

export type BreakdownScope = "global" | "org" | "class";
export type BreakdownStatus = "draft" | "published" | "deleted";

export interface Breakdown {
  id: UUID;
  scope: BreakdownScope;
  scope_ref_id: UUID | null;
  curriculum_id: UUID;
  grade_id: UUID;
  subject_id: UUID;
  book_id: UUID | null;
  parent_breakdown_id: UUID | null;
  previous_version_id: UUID | null;
  status: BreakdownStatus;
  total_teaching_days: number | null;
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

export interface TodayEntry {
  cst_id: UUID;
  subject_id: UUID;
  subject_code: string;
  grade_id: UUID;
  grade_code: number;
  day_number: number | null;
  lesson_slot: LessonSlotEntry | null;
  assessment_slot: AssessmentSlotEntry | null;
  previous_taught: PreviousTaughtSummary | null;
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

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  /** Set to false if the endpoint is webhook/refresh and doesn't need X-API-Key. */
  authed?: boolean;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", query, body, authed = true } = opts;
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
  if (authed) {
    const key = getApiKey();
    if (!key) {
      throw new DarsApiError(
        401,
        "missing api key — set localStorage.dars_org_api_key first",
        url,
      );
    }
    headers["X-API-Key"] = key;
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
// Breakdowns (`/api/v2/*`)
// ---------------------------------------------------------------------------

export interface BreakdownWithChapters extends Breakdown {
  chapters: {
    id: UUID;
    breakdown_id: UUID;
    book_chapter_id: UUID;
    position: number;
    teaching_days: number;
  }[];
}

export const breakdowns = {
  getBreakdowns: (params: { scope?: BreakdownScope; scope_ref_id?: UUID; status?: string } = {}) =>
    request<ListResponse<Breakdown>>("/api/v2/breakdowns", { query: params }),

  /** Single breakdown read returns chapters + slots hydrated. */
  getBreakdown: (id: UUID) =>
    request<BreakdownWithChapters>(`/api/v2/breakdowns/${id}`),

  /** Convenience: most-recent published class-scope breakdown for the CST. */
  getMyClassBreakdown: async (cst_id: UUID): Promise<Breakdown | null> => {
    const res = await breakdowns.getBreakdowns({ scope: "class", scope_ref_id: cst_id });
    const published = res.items.find((b) => b.status === "published");
    return published ?? null;
  },
};

// ---------------------------------------------------------------------------
// Class slots + actions (`/api/v2/*` for actions, `/api/v1/*` for detail)
// ---------------------------------------------------------------------------

export const slots = {
  /** F3.13 — full slot detail with LP status + content. */
  getLessonSlotDetail: (slot_id: UUID) =>
    request<ClassLessonSlotDetail>(`/api/v1/class-lesson-slots/${slot_id}`),

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
};

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
  /** week_start: a Monday in ISO date format. Defaults to "this week" on the server. */
  get: (week_start?: ISODate) =>
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
  curriculum_code: string;
  grade: number;
  subject: string;
  page_content: string;
  lp_type: string;
  class_strength?: number;
  generate_bilingual?: boolean;
}

export interface QuickExamBody {
  curriculum_code: string;
  grade: number;
  subject: string;
  page_content: string;
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
// Default export bundles every namespace for ergonomic imports
// ---------------------------------------------------------------------------

export const darsApi = {
  tenancy,
  curriculum,
  books,
  breakdowns,
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
  // utilities
  getApiKey,
  setApiKey,
  clearApiKey,
};

export default darsApi;
