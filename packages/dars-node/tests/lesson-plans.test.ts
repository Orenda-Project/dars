import { describe, it, expect, vi, beforeEach } from 'vitest'
import { LessonPlansResource } from '../src/lesson-plans'
import { DarsAuthError, DarsNotFoundError, DarsValidationError } from '../src/errors'

const BASE_URL = 'https://api.dars.taleemabad.com'
const API_KEY = 'sk_test'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

function mockResponse(body: unknown, status = 200) {
  mockFetch.mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  })
}

const fakeLp = {
  id: 'abc-123',
  client_id: 'client-1',
  external_ref: null,
  grade: '3',
  subject: 'Maths',
  topic: null,
  page_number: '10',
  class_strength: null,
  content: '<html>LP</html>',
  content_bilingual: null,
  status: 'completed',
  metadata_: {},
  tags: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

describe('LessonPlansResource', () => {
  let resource: LessonPlansResource

  beforeEach(() => {
    mockFetch.mockReset()
    resource = new LessonPlansResource(BASE_URL, API_KEY)
  })

  describe('create', () => {
    it('POSTs to /api/v1/lesson-plans with correct headers and body', async () => {
      mockResponse(fakeLp, 201)

      const result = await resource.create({
        grade: '3',
        subject: 'Maths',
        page_number: '10',
      })

      expect(mockFetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/v1/lesson-plans`,
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json',
          }),
          body: JSON.stringify({
            grade: '3',
            subject: 'Maths',
            page_number: '10',
          }),
        })
      )
      expect(result.id).toBe('abc-123')
    })

    it('throws DarsAuthError on 401', async () => {
      mockResponse({ detail: 'Unauthorized' }, 401)
      await expect(resource.create({ grade: '3', subject: 'Maths', page_number: '10' }))
        .rejects.toBeInstanceOf(DarsAuthError)
    })

    it('throws DarsValidationError on 422 with field message', async () => {
      mockResponse({ detail: [{ loc: ['body', 'grade'], msg: 'field required' }] }, 422)
      const err = await resource.create({ grade: '3', subject: 'Maths', page_number: '10' })
        .catch(e => e)
      expect(err).toBeInstanceOf(DarsValidationError)
      expect(err.message).toContain('grade')
    })

    it('throws DarsApiError on unexpected 500', async () => {
      mockResponse({ detail: 'Internal server error' }, 500)
      const err = await resource.create({ grade: '3', subject: 'Maths', page_number: '10' })
        .catch(e => e)
      expect(err.status).toBe(500)
    })
  })

  describe('list', () => {
    it('GETs /api/v1/lesson-plans with limit and offset', async () => {
      mockResponse({ items: [fakeLp], total: 1 })

      const result = await resource.list({ limit: 10, offset: 5 })

      expect(mockFetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/v1/lesson-plans?limit=10&offset=5`,
        expect.objectContaining({
          method: 'GET',
          headers: expect.objectContaining({ 'X-API-Key': API_KEY }),
        })
      )
      expect(result.items).toHaveLength(1)
      expect(result.total).toBe(1)
    })

    it('uses default limit/offset when not provided', async () => {
      mockResponse({ items: [], total: 0 })
      await resource.list()
      const url = mockFetch.mock.calls[0][0] as string
      expect(url).toContain('limit=20')
      expect(url).toContain('offset=0')
    })
  })

  describe('get', () => {
    it('GETs /api/v1/lesson-plans/:id', async () => {
      mockResponse(fakeLp)
      const result = await resource.get('abc-123')
      expect(mockFetch).toHaveBeenCalledWith(
        `${BASE_URL}/api/v1/lesson-plans/abc-123`,
        expect.objectContaining({ method: 'GET' })
      )
      expect(result.id).toBe('abc-123')
    })

    it('throws DarsNotFoundError on 404', async () => {
      mockResponse({ detail: 'Not found' }, 404)
      await expect(resource.get('bad-id')).rejects.toBeInstanceOf(DarsNotFoundError)
    })
  })
})
