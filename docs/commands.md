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
make db-push      # Apply pending migrations to Supabase
make db-pull      # Pull schema changes from Supabase dashboard
make db-status    # Check migration status
make db-new       # Create new migration file (prompts for name)
make db-link      # Link to a Supabase project (needs SUPABASE_PROJECT_REF)
```

Migrations: plain SQL files in `supabase/migrations/` named `YYYYMMDDHHMMSS_description.sql`.

## Webapp

```bash
make webapp       # Run Next.js dev server (webapp/)
```

## Supabase environments

| Env | Status | Use |
|-----|--------|-----|
| `dars-dev` | Active | Remote Supabase, used for development |
| `dars-prod` | Not created | Will be separate project for production |
| `dars-local` | Not set up | Will use `supabase start` (Docker) |

Switch: `supabase link --project-ref <ref>` then `make db-push`. Each env gets its own `DATABASE_URL`.
