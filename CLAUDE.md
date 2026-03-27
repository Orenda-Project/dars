# Dars — Project Memory

## What this is
Dars (درس, "lesson") is a standalone B2B service that provides lesson plan (LP) creation and rendering infrastructure for Taleemabad internal teams. It is NOT a monolith — it is a focused service with a documented API and reusable npm packages.

## Repo layout
- `api/` — FastAPI backend (Python 3.12, SQLAlchemy async, asyncpg)
- `packages/dars-client/` — TypeScript API client (`@dars/client`)
- `packages/dars-react/` — React components (`@dars/react`)
- `supabase/` — Database migrations managed by Supabase CLI
- `docs/ROADMAP.md` — Phased roadmap; re-read after each phase to reflect and adjust
- `docs/context/` — Stable background: company context, LP assistant API, vocabulary
- `docs/WRITING_DOCS.md` — Conventions for writing docs in this repo
- `docs/superpowers/specs/` — Design specs
- `docs/superpowers/plans/` — Implementation plans
- `docs/adr/` — Architecture Decision Records

## Key decisions
- **FastAPI** over Django REST — async-native, auto OpenAPI, lighter
- **Supabase** (hosted Postgres) — no local DB container, dashboard for inspection
- **Row-level isolation** — `client_id` FK on all data tables, no schema-per-tenant
- **API keys** — SHA-256 hashed, shown once on creation, never stored plain
- **BackgroundTasks** — no Celery; FastAPI built-in is sufficient for now
- **LP Assistant** — AI generation delegated to `lp-assistant.taleemabad.com` for now

## Commands
```bash
# First-time setup
cd api && uv sync --extra dev

# Run API (dev) — requires api/.env to exist
make dev

# Run tests
make test

# Apply DB migrations
make db-push

# Check migration status
make db-status

# Pull schema changes from remote (if you edited via Supabase dashboard)
make db-pull

# Create a new migration file (prompts for name)
make db-new

# Build client package
cd packages/dars-client && pnpm build

# Build react package
cd packages/dars-react && pnpm build
```

## Environment
Copy `api/.env.example` to `api/.env` and fill in values before running. Required vars: `DATABASE_URL`, `ADMIN_SECRET`.

### Supabase environments
- **dars-dev** — remote Supabase project, used for active development (currently the only one)
- **dars-prod** — not yet created; will be a separate Supabase project for production
- **dars-local** — not yet set up; will use `supabase start` (Docker) for offline dev

Switch environments: `supabase link --project-ref <ref>` then `supabase db push`. Each env gets its own `DATABASE_URL`.

## Keeping docs current
- When new or corrected information about Taleemabad (teams, services, vocabulary) comes up in conversation, update `docs/context/taleemabad.md` immediately — don't wait to be asked.
- When a roadmap phase completes, update `docs/ROADMAP.md` status and reflect before proceeding.

## Conventions
- All DB models in `models.py`, Pydantic schemas in `schemas.py`, business logic in `service.py`
- Every public endpoint requires `X-API-Key` header — enforced in `deps.py:get_current_client`
- Admin endpoints (client management) require `X-Admin-Secret` header
- All DB queries must filter by `client_id` — never query without it on data tables
- UUIDs everywhere for IDs
- Migrations go in `supabase/migrations/` as plain SQL files named `YYYYMMDDHHMMSS_description.sql`
- Tests use an in-memory SQLite via `aiosqlite` — no real Supabase connection needed for tests

## Gotchas
- Use `sqlalchemy.types.Uuid` NOT `sqlalchemy.dialects.postgresql.UUID` — the PG dialect breaks SQLite tests
- Always use `hmac.compare_digest` for secret/token string comparison — plain `!=` is timing-attackable
- `settings` is a module-level singleton instantiated at import time — tests cannot override env vars after first import
- Test DB fixtures must declare `scope="function"` explicitly to prevent data bleed if scope is changed later
- `*.db` files are gitignored — SQLite test.db is created by the default `database_url` config

See `docs/ROADMAP.md` for current status and what's next.
