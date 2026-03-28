/**
 * Parameters for creating a new lesson plan.
 * All fields map directly to the Dars API request body.
 */
export interface CreateLessonPlanParams {
  /** Grade level, e.g. "3", "KG", "1" */
  grade: string
  /** Subject name, e.g. "Maths", "Eng", "Urdu", "Science" */
  subject: string
  /** Textbook page number(s), e.g. "10" or "10-12" */
  page_number: string
  /** Curriculum type. Defaults to "ICT" (national). Use "Punjab" for provincial. */
  curriculum?: 'ICT' | 'Punjab'
  /** Number of students in the class */
  class_strength?: number
  /** Optional topic override */
  topic?: string
  /** Your own reference ID for this LP — stored and returned as-is */
  external_ref?: string
  /** Exercise page number(s), if different from main page */
  exercise_page_number?: string
  /** Custom instructions passed to the LP generator */
  custom_prompt?: string
  /** Generate both English and Urdu versions. Defaults to false. */
  generate_bilingual?: boolean
  /** Enable extended reasoning in the generator. Defaults to true. */
  reasoning_enabled?: boolean
}

/**
 * Options for listing lesson plans.
 */
export interface ListLessonPlansOptions {
  /** Maximum number of results to return. Default: 20, max: 100. */
  limit?: number
  /** Number of results to skip for pagination. Default: 0. */
  offset?: number
}

/**
 * A lesson plan returned by the Dars API.
 */
export interface LessonPlan {
  /** Unique ID of this lesson plan */
  id: string
  /** ID of the client that owns this LP */
  client_id: string
  /** Your own reference ID, if provided at creation */
  external_ref: string | null
  grade: string
  subject: string
  topic: string | null
  page_number: string | null
  class_strength: number | null
  /** HTML content of the lesson plan. Null if generation failed or is pending. */
  content: string | null
  /** Bilingual (Urdu) HTML content. Null if not requested or not yet generated. */
  content_bilingual: string | null
  /** Current status: "pending" | "completed" | "failed" */
  status: string
  /** Internal metadata (generation timings, token costs, etc.) */
  metadata_: Record<string, unknown>
  /** Curriculum tags extracted during generation */
  tags: Record<string, unknown>
  created_at: string
  updated_at: string
}

/**
 * Result from listing lesson plans.
 */
export interface ListLessonPlansResult {
  items: LessonPlan[]
  /** Total number of LPs for this client (useful for pagination) */
  total: number
}

/**
 * Configuration for the DarsClient.
 */
export interface DarsClientConfig {
  /** Your Dars secret API key (sk_xxx). Never expose this in the browser. */
  apiKey: string
  /**
   * Base URL of the Dars API.
   * @default "https://api.dars.taleemabad.com"
   */
  baseUrl?: string
}
