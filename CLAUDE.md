# Dars — Claude Operating Manual

**Purpose:** Standalone B2B service for lesson plan creation and rendering. Not a monolith.

---

## Quick Navigation

| Looking for... | Go to... |
|----------------|----------|
| **🔥 ACTIVE: v2 rebuild — single-pointer onramp** | **[REBUILD.md](REBUILD.md)** |
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
| `server/src/dars/migrations/` | DB migrations (plain SQL) — **all `.sql` migration files go here, nowhere else** |
| `webapp/` | Next.js web app |
| `docs/` | All project documentation |
| `.beads/` | Work tracking (append-only JSONL) |
| `.claude/hooks/` | Lifecycle hooks |

---

## Skills

| Skill | When to use |
|-------|-------------|
| `/feature <name>` | Start any new feature — research → plan (doc for review) → implement + e2e |
| `/retrospect` | End of session — analyze what could have been done better, append suggestions to `.claude/improvements.md` |

Use the Agent tool for any self-contained backend or frontend build that would otherwise pollute the main conversation context with implementation detail. Good signals: large rewrites, anything touching >4 files. Return a summary; don't narrate every file change inline.

---

## Critical Rules

1. **Always work on a feature branch** — never commit directly to `main`; branch naming: `feature/<slug>` or `fix/<slug>`
2. **Never `git push` without explicit user confirmation** — `main` deploys directly to production on Railway. Stage the commit, show the diff, and wait for the user to say "ship it" or "push" before running `git push`. PRs always target `staging`.
3. **All DB queries must filter by `client_id`** — never query data tables without it
4. **Never store API keys plain** — SHA-256 hash on creation, shown once only
5. **Use `hmac.compare_digest`** for all secret comparisons — plain `!=` is timing-attackable
6. **Use `sqlalchemy.types.Uuid`** not `sqlalchemy.dialects.postgresql.UUID` — PG dialect breaks SQLite tests
7. **Never run DDL or migrations manually** — no `psql` DDL, no local migration commands. Migrations run automatically on Railway deployment. Write the `.sql` file; the deploy applies it.
8. **Open a bead before starting any non-trivial task** — see [.beads/README.md](.beads/README.md)
9. **Design work:** read `theme.pen` via pencil MCP before touching colors or typography
10. **Check deferred tools before claiming unavailability** — before telling the user you cannot access a service or tool, check the deferred tools list in the system-reminder. If a relevant MCP tool is listed, use ToolSearch to load its schema and proceed. Never say "I can't access X" without checking first.
11. **Structured logging on every flow** — every service function, endpoint, and background task must log:
    - Entry at `INFO` with relevant IDs and input context
    - Exit/completion at `INFO` with status and key output (counts, IDs)
    - Errors at `ERROR` with `exc_info=True`
    - Use `logger = logging.getLogger(__name__)` — never `print()`
12. **Default execution mode: autonomous** — never pause to confirm understanding before proceeding. Just proceed; the user will redirect if needed. The only valid exception is a genuine blocker (missing spec, missing credential).
13. **No pre-action narration** — never write "I'll now X" or "Let me Y" before a tool call. Do X, then state the result. Output text that reports findings, not announces intentions.
14. **After any PR merge — poll Railway automatically** — if Railway MCP is in the deferred tools list, immediately use `mcp__Railway__list-deployments` to find the latest deployment and begin polling. Do not wait for the user to ask.
15. **Before editing a file modified earlier in the same session, re-read it first** — never assume file state matches your earlier write.

---

## Webapp Architecture

The webapp has two distinct parts — never conflate them:

| Part | Route | Purpose | User |
|------|-------|---------|------|
| **Client Dashboard** | `/dashboard/...` | Configuration + monitoring. API key management, academic year setup, classes, teachers, usage. The client is a developer who integrates Dars APIs into their own app. | School admin / developer |
| **Teacher Sample App** | `/teacher-app/...` | A complete, functioning sample integration showing what a teacher's experience could look like. Uses the client's `default_teacher_id`. Demonstrates: today's classes, lesson breakdown, mark as taught, assessments. | Demo for client — shows what to build |

The division must be visually and structurally clear. `/teacher-app` is not part of the dashboard — it's a standalone demo app that happens to share the same API key from the session.

---

## Harness Rules

- **All harness lives inside this repo** — never write project context to `~/.claude/` or any path outside `/home/hataf/taleemabad/dars/`. Notes → `.claude/improvements.md`. Context → `docs/`. Work tracking → `.beads/`.
- **Alignment/intent questions** — answer from known context first; only read files if the answer depends on implementation details not already in conversation.

---

## Key Decisions (summary)

FastAPI (async-native) · Supabase (hosted Postgres) · Row-level multitenancy via `client_id` · API keys over JWT · LP generation delegated to LP Assistant (Phase 1), absorbed in Phase 2

Full rationale: [docs/adr/README.md](docs/adr/README.md)

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
