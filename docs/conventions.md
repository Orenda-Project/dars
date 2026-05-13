---
type: reference
last_verified: 2026-04-08
owner: hataf
---

# Dars — Conventions & Gotchas

## Code conventions

- All DB models in `models.py`, Pydantic schemas in `schemas.py`, business logic in `service.py`
- Every public endpoint requires `X-API-Key` header — enforced in `deps.py:get_current_client`
- Admin endpoints (client management) require `X-Admin-Secret` header
- All DB queries must filter by `client_id` — never query without it on data tables
- UUIDs everywhere for IDs
- Migrations go in `server/src/dars/migrations/` as plain SQL files named `YYYYMMDDHHMMSS_description.sql`
- Tests use an in-memory SQLite via `aiosqlite` — no real DB connection needed for tests
- **API key format:** `dars_<urlsafe-base64>` — the prefix is `dars_`, not `drs_live_` or any other variant
- **Webapp copy voice:** leads with teacher value first; FDS/API teams get a dedicated heavy section but are not the headline audience

## Gotchas

- Use `sqlalchemy.types.Uuid` NOT `sqlalchemy.dialects.postgresql.UUID` — the PG dialect breaks SQLite tests
- Always use `hmac.compare_digest` for secret/token string comparison — plain `!=` is timing-attackable
- `settings` is a module-level singleton instantiated at import time — tests cannot override env vars after first import
- Test DB fixtures must declare `scope="function"` explicitly to prevent data bleed if scope is changed later
- `*.db` files are gitignored — SQLite test.db is created by the default `database_url` config
- Migration filenames must be unique — two files with the same `YYYYMMDDHHMMSS` prefix will conflict; increment the sequence suffix (`000001`, `000002`) within the same day
- `curriculum` is not stored on the `LessonPlan` model — the edit flow defaults to `"ICT"`; fix tracked in roadmap
- `lesson_plan_edits` is append-only history — each edit saves `content_before` + `content_bilingual_before` before overwriting `lp.content`; last-row wins for current state

## Database migrations

Always:
1. Create a migration file: `make db-new` (prompts for name, creates the file)
2. Write the SQL in `server/src/dars/migrations/YYYYMMDDHHMMSS_name.sql`
3. Apply via `make db-migrate` (or just start the server — migrations run on startup)

Works against any PostgreSQL URL (Railway prod, Railway staging, local). Set `DATABASE_URL` in `server/.env` to target the right environment.

## Keeping docs current

- When new or corrected information about Taleemabad comes up, update [`docs/context/taleemabad.md`](context/taleemabad.md) immediately
- When a roadmap phase completes, update [`docs/ROADMAP.md`](ROADMAP.md) and reflect before proceeding
