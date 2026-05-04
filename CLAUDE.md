# Dars — Claude Operating Manual

**Purpose:** Standalone B2B service for lesson plan creation and rendering. Not a monolith.

---

## Quick Navigation

| Looking for... | Go to... |
|----------------|----------|
| Current phase, what's next | [docs/ROADMAP.md](docs/ROADMAP.md) |
| Dev commands, env setup | [docs/commands.md](docs/commands.md) |
| Code conventions, gotchas | [docs/conventions.md](docs/conventions.md) |
| Design tokens, typography | [docs/design-system.md](docs/design-system.md) |
| Company context, LP assistant API | [../docs/context/taleemabad.md](../docs/context/taleemabad.md) |
| Architecture decisions | [docs/adr/README.md](docs/adr/README.md) |
| Feature specs | [docs/specs/README.md](docs/specs/README.md) |
| Implementation plans | [docs/plans/README.md](docs/plans/README.md) |
| Active work / open beads | [.beads/status.jsonl](.beads/status.jsonl) |
| How to write docs | [docs/WRITING_DOCS.md](docs/WRITING_DOCS.md) |

---

## Repo Layout

| Folder | Contents |
|--------|----------|
| `server/` | FastAPI backend (Python 3.12, SQLAlchemy async, asyncpg) |
| `supabase/migrations/` | DB migrations (Supabase CLI) — **all `.sql` migration files go here, not `server/`** |
| `webapp/` | Next.js web app |
| `docs/` | All project documentation |
| `.beads/` | Work tracking (append-only JSONL) |
| `.claude/hooks/` | Lifecycle hooks |

---

## Agent usage

Use the Agent tool for any self-contained backend or frontend build that would otherwise pollute the main conversation context with implementation detail. Good signals: building a new module end-to-end, large deletions/rewrites, anything that touches >4 files. Return a summary to the main conversation; don't narrate every file change inline.

---

## Critical Rules

1. **Always work on a feature branch** — never commit directly to `main`; branch naming: `feature/<slug>` or `fix/<slug>`
2. **Never `git push` without explicit user confirmation** — `main` deploys directly to production on Railway. Stage the commit, show the diff, and wait for the user to say "ship it" or "push" before running `git push`.
2. **All DB queries must filter by `client_id`** — never query data tables without it
3. **Never store API keys plain** — SHA-256 hash on creation, shown once only
4. **Use `hmac.compare_digest`** for all secret comparisons — plain `!=` is timing-attackable
5. **Use `sqlalchemy.types.Uuid`** not `sqlalchemy.dialects.postgresql.UUID` — PG dialect breaks SQLite tests
6. **Open a bead before starting any non-trivial task** — see [.beads/README.md](.beads/README.md)
7. **Design work:** read `theme.pen` via pencil MCP before touching colors or typography
8. **Structured logging on every flow** — every service function, endpoint, and background task must log:
   - Entry at `INFO` with relevant IDs and input context
   - Exit/completion at `INFO` with status and key output (counts, IDs)
   - Errors at `ERROR` with `exc_info=True`
   - Use `logger = logging.getLogger(__name__)` — never `print()`

---

## Key Decisions (summary)

FastAPI (async-native) · Supabase (hosted Postgres) · Row-level multitenancy via `client_id` · API keys over JWT · LP generation delegated to LP Assistant (Phase 1), absorbed in Phase 2

Full rationale: [docs/adr/README.md](docs/adr/README.md)
