import { DarsApiError, DarsAuthError, DarsNotFoundError, DarsValidationError } from './errors.js'
import type {
  CreateLessonPlanParams,
  LessonPlan,
  ListLessonPlansOptions,
  ListLessonPlansResult,
} from './types.js'

/**
 * Provides methods for creating, listing, and retrieving lesson plans.
 * Access via `dars.lessonPlans`.
 */
export class LessonPlansResource {
  constructor(
    private readonly baseUrl: string,
    private readonly apiKey: string,
  ) {}

  private async request<T>(
    path: string,
    options: RequestInit & { params?: Record<string, string | number> } = {},
  ): Promise<T> {
    const { params, ...fetchOptions } = options
    let url = `${this.baseUrl}${path}`
    if (params) {
      const qs = new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)]),
      )
      url += `?${qs.toString()}`
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers: {
        'X-API-Key': this.apiKey,
        ...fetchOptions.headers,
      },
    })

    const body = await response.json()

    if (!response.ok) {
      if (response.status === 401) throw new DarsAuthError()
      if (response.status === 404) throw new DarsNotFoundError('lesson plan')
      if (response.status === 422) {
        const detail = body?.detail
        let msg = 'Validation error'
        if (Array.isArray(detail) && detail.length > 0) {
          const field = detail[0]?.loc?.slice(1).join('.') ?? 'unknown'
          const issue = detail[0]?.msg ?? 'invalid'
          msg = `'${field}': ${issue}`
        }
        throw new DarsValidationError(msg)
      }
      throw new DarsApiError(body?.detail ?? 'Unexpected error', response.status)
    }

    return body as T
  }

  /**
   * Generate a new lesson plan. Takes approximately 60 seconds to complete.
   * The LP is stored in Dars and returned once generation finishes.
   *
   * @example
   * const lp = await dars.lessonPlans.create({ grade: '3', subject: 'Maths', page_number: '10' })
   */
  async create(params: CreateLessonPlanParams): Promise<LessonPlan> {
    return this.request<LessonPlan>('/api/v1/lesson-plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(params),
    })
  }

  /**
   * List lesson plans for your client, newest first.
   *
   * @example
   * const { items, total } = await dars.lessonPlans.list({ limit: 10, offset: 0 })
   */
  async list(options: ListLessonPlansOptions = {}): Promise<ListLessonPlansResult> {
    const { limit = 20, offset = 0 } = options
    return this.request<ListLessonPlansResult>('/api/v1/lesson-plans', {
      method: 'GET',
      params: { limit, offset },
    })
  }

  /**
   * Retrieve a single lesson plan by ID.
   *
   * @param id - The lesson plan UUID returned from `create` or `list`
   * @throws {DarsNotFoundError} if the LP does not exist or belongs to another client
   */
  async get(id: string): Promise<LessonPlan> {
    return this.request<LessonPlan>(`/api/v1/lesson-plans/${id}`, {
      method: 'GET',
    })
  }
}
