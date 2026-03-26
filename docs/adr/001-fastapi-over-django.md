# ADR-001: FastAPI over Django REST Framework

**Status:** Accepted
**Date:** 2026-03-26

## Context
Dars is an independent service, not a monolith feature. The existing taleemabad-core uses Django REST Framework. We need to choose a Python web framework for Dars.

## Decision
Use FastAPI.

## Reasons
- Async-native: lesson plan generation involves waiting on an external AI service; async handles this without thread pool overhead
- Auto-generates OpenAPI/Swagger from code — documentation is a first-class concern for a B2B SDK service
- Lighter than Django: no ORM coupling, no admin, no templating — we only need an API
- pydantic-settings gives clean 12-factor config
- Easier to write and test async code than Django's sync-by-default model

## Consequences
- Team must learn FastAPI patterns (dependency injection, lifespan events) instead of Django patterns
- SQLAlchemy replaces Django ORM — more verbose but more explicit
- No Django admin — internal client management done via API endpoint
