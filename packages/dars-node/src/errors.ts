/**
 * Base error class for all Dars API errors.
 * Check `error.status` for the HTTP status code.
 */
export class DarsApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'DarsApiError'
    this.status = status
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Thrown when the API key is missing or invalid.
 * Check your DARS_SECRET_KEY environment variable.
 */
export class DarsAuthError extends DarsApiError {
  constructor(message = 'Invalid API key. Get your key from the Dars admin panel.') {
    super(message, 401)
    this.name = 'DarsAuthError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Thrown when request parameters fail validation.
 * `error.message` names the specific field and what's wrong.
 */
export class DarsValidationError extends DarsApiError {
  constructor(message: string) {
    super(message, 422)
    this.name = 'DarsValidationError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Thrown when the requested resource (e.g. lesson plan) does not exist.
 */
export class DarsNotFoundError extends DarsApiError {
  constructor(resource: string) {
    super(`${resource} not found`, 404)
    this.name = 'DarsNotFoundError'
    Object.setPrototypeOf(this, new.target.prototype)
  }
}
