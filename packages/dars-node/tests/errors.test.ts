import { describe, it, expect } from 'vitest'
import {
  DarsApiError,
  DarsAuthError,
  DarsValidationError,
  DarsNotFoundError,
} from '../src/errors'

describe('DarsApiError', () => {
  it('is an instance of Error', () => {
    const e = new DarsApiError('something failed', 500)
    expect(e).toBeInstanceOf(Error)
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e.message).toBe('something failed')
    expect(e.status).toBe(500)
    expect(e.name).toBe('DarsApiError')
  })
})

describe('DarsAuthError', () => {
  it('extends DarsApiError with status 401', () => {
    const e = new DarsAuthError()
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e).toBeInstanceOf(DarsAuthError)
    expect(e.status).toBe(401)
    expect(e.message).toBe('Invalid API key. Get your key from the Dars admin panel.')
    expect(e.name).toBe('DarsAuthError')
  })

  it('accepts a custom message', () => {
    const e = new DarsAuthError('custom message')
    expect(e.message).toBe('custom message')
  })
})

describe('DarsValidationError', () => {
  it('extends DarsApiError with status 422', () => {
    const e = new DarsValidationError("'grade' is required")
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e).toBeInstanceOf(DarsValidationError)
    expect(e.status).toBe(422)
    expect(e.message).toBe("'grade' is required")
    expect(e.name).toBe('DarsValidationError')
  })
})

describe('DarsNotFoundError', () => {
  it('extends DarsApiError with status 404', () => {
    const e = new DarsNotFoundError('lesson plan')
    expect(e).toBeInstanceOf(DarsApiError)
    expect(e).toBeInstanceOf(DarsNotFoundError)
    expect(e.status).toBe(404)
    expect(e.message).toBe("lesson plan not found")
    expect(e.name).toBe('DarsNotFoundError')
  })
})
