# ADR-003: Supabase for Database Hosting

**Status:** Accepted
**Date:** 2026-03-26

## Context
We need a PostgreSQL database. Options: self-hosted Docker, managed RDS, or Supabase.

## Decision
Use Supabase hosted PostgreSQL.

## Reasons
- No local database container needed — developers just copy `.env.example` and fill in credentials
- Supabase dashboard provides a table viewer and SQL editor for quick inspection
- Free tier is sufficient for early development
- Supabase CLI allows migrations to be managed in code (`supabase/migrations/`)
- Standard PostgreSQL under the hood — can migrate away if needed

## Consequences
- Developers need a Supabase project (created once manually in the dashboard)
- Supabase project ref and DB password must be shared with team via secure channel
- Internet required for local dev (no offline DB option without Docker)
