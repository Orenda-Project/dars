---
type: runbook
last_verified: 2026-04-08
owner: hataf
---

# Dars — Dev Commands & Environment

## Setup

```bash
# First-time setup
cd server && uv sync --extra dev

# Copy env file
cp server/.env.example server/.env
# Fill in: DATABASE_URL, ADMIN_SECRET
```

## Daily commands

```bash
make up           # Run API + webapp together (Ctrl+C stops both)
make dev          # Run API only (dev) — hot reload
make test         # Run test suite (SQLite, no Supabase needed)
```

## Database

```bash
make db-migrate   # Apply pending migrations to the configured DATABASE_URL
make db-new       # Create a new empty migration file (prompts for name)
```

Migrations are plain SQL files in `server/src/dars/migrations/` named `YYYYMMDDHHMMSS_description.sql`.

The migration runner (`server/src/dars/migrations.py`) tracks applied migrations in a `schema_migrations` table and runs any pending ones on app startup as well. Works against any PostgreSQL URL — Railway (prod/staging), local Docker, or any other Postgres instance.

Set `DATABASE_URL` in `server/.env` to point at whichever environment you want to migrate.

## Webapp

```bash
make webapp       # Run Next.js dev server (webapp/)
```
