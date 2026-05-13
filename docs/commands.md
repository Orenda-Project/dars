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
make db-new       # Create a new empty migration file (prompts for name)
```

Migrations are plain SQL files in `server/src/dars/migrations/` named `YYYYMMDDHHMMSS_description.sql`.

The migration runner (`server/src/dars/migrations.py`) runs automatically on app startup — it picks up any pending migrations and applies them. **Never run migrations manually via psql or any local command.** Migrations only run via Railway deployment (staging or production).

## Webapp

```bash
make webapp       # Run Next.js dev server (webapp/)
```
