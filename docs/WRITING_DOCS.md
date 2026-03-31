# How to Write Dars Documentation

## Purpose
This file governs how documentation is written and organized in this repo. Its goal: keep AI context lean while making knowledge discoverable on demand.

## Principles
- **One concern per file.** Don't mix company context with API specs or implementation plans.
- **Summaries in MEMORY.md, details in files.** The memory index should be ≤ one line per entry. Full content lives in the linked file.
- **Link don't duplicate.** If something is already in CLAUDE.md or an ADR, point to it — don't repeat it.
- **Stable facts vs. volatile facts.** Long-lived context (company background, architecture decisions) goes in `docs/context/`. In-flight work (plans, specs) goes in `docs/superpowers/`.

## Directory layout
```
docs/
├── WRITING_DOCS.md          ← this file
├── context/                 ← stable background knowledge
│   └── taleemabad.md        ← company, teams, operations context
├── adr/                     ← architecture decision records (one per decision)
└── superpowers/
    ├── specs/               ← design specs (input to planning)
    └── plans/               ← implementation plans (input to execution)
```

## File naming
- Context files: `<topic>.md` (lowercase, hyphenated)
- ADRs: `NNN-short-title.md`
- Specs: `YYYY-MM-DD-<feature>.md`
- Plans: `YYYY-MM-DD-plan-<label>.md`

## What goes where
| Content type | Location |
|---|---|
| Company background, teams, vocabulary | `docs/context/taleemabad.md` |
| Architecture decisions + rationale | `docs/adr/` |
| Feature design / requirements | `docs/superpowers/specs/` |
| Step-by-step implementation plans | `docs/superpowers/plans/` |
| Project-wide conventions, gotchas | `CLAUDE.md` |
| Personal notes, cheat sheets, decisions | `docs/personal/` |
| Memory index | `~/.claude/projects/.../MEMORY.md` |

## When to read a doc
Don't load context docs preemptively. Load them when:
- The task touches the domain the doc covers
- A memory index entry says "see docs/context/X.md for details"

## Personal notes (`docs/personal/`)

For human reading only — not referenced by CLAUDE.md or memory. Use judgment on placement:

- **Dedicated file** (`docs/personal/<topic>.md`) — when the topic is substantial enough to stand on its own (e.g. a full primer, a detailed cheat sheet, a significant decision with context). If in doubt, dedicated file.
- **Append to `notes.md`** — for short, miscellaneous items that don't warrant their own file (a quick decision, a one-liner reminder, a small table).

If the topic size is ambiguous, ask before creating.

## Keeping docs current
- Update a doc when facts in it change — don't leave stale content.
- If a plan is fully executed, mark it complete at the top rather than deleting it.
