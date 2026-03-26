# ADR-002: Row-Level Multi-Tenancy

**Status:** Accepted
**Date:** 2026-03-26

## Context
Multiple internal teams (Punjab, Sindh, etc.) will use Dars. Their data must be isolated — one team cannot see another's lesson plans.

## Decision
Use row-level isolation: every data table has a `client_id` UUID foreign key. All queries filter by `client_id`. Single schema, single database.

## Reasons
- Simpler than schema-per-tenant (no per-tenant migrations, no connection switching)
- Sufficient for internal B2B — teams are Taleemabad employees, not untrusted external customers
- PostgreSQL RLS (Row Level Security) can be added later as an extra safety layer
- Easier to query across clients for analytics if ever needed

## Consequences
- Developers must remember to always filter by `client_id` — enforced via the `get_current_client` dependency
- A bug that forgets `client_id` could expose cross-tenant data — mitigated by code review and tests
