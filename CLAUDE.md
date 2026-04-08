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
| Company context, LP assistant API | [docs/context/taleemabad.md](docs/context/taleemabad.md) |
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
| `supabase/` | DB migrations (Supabase CLI) |
| `webapp/` | Next.js web app |
| `docs/` | All project documentation |
| `.beads/` | Work tracking (append-only JSONL) |
| `.claude/hooks/` | Lifecycle hooks |

---

## Critical Rules

1. **All DB queries must filter by `client_id`** — never query data tables without it
2. **Never store API keys plain** — SHA-256 hash on creation, shown once only
3. **Use `hmac.compare_digest`** for all secret comparisons — plain `!=` is timing-attackable
4. **Use `sqlalchemy.types.Uuid`** not `sqlalchemy.dialects.postgresql.UUID` — PG dialect breaks SQLite tests
5. **Open a bead before starting any non-trivial task** — see [.beads/README.md](.beads/README.md)
6. **Design work:** read `theme.pen` via pencil MCP before touching colors or typography

---

## Key Decisions (summary)

FastAPI (async-native) · Supabase (hosted Postgres) · Row-level multitenancy via `client_id` · API keys over JWT · LP generation delegated to LP Assistant (Phase 1), absorbed in Phase 2

Full rationale: [docs/adr/README.md](docs/adr/README.md)
