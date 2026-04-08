---
type: reference
last_verified: 2026-04-08
owner: hataf
---

# How to Write Dars Documentation

## Principles

- **One concern per file.** Don't mix company context with API specs or implementation plans.
- **L1 routes, L3 contains.** CLAUDE.md is a routing table — zero substantive content. Details live in L3 docs.
- **Link don't duplicate.** If something is in an ADR, point to it.
- **Stable vs. volatile.** Long-lived context goes in `docs/context/`. In-flight work goes in `docs/specs/` and `docs/plans/`.

## Directory layout

```
docs/
├── README.md                ← L2 router for docs/
├── ROADMAP.md               ← Current phase and status
├── WRITING_DOCS.md          ← This file
├── conventions.md           ← Code conventions and gotchas
├── commands.md              ← Dev commands and environment
├── design-system.md         ← Colors, typography, visual language
├── context/
│   ├── README.md            ← L2 router
│   └── taleemabad.md        ← Company, teams, LP assistant API
├── adr/
│   ├── README.md            ← L2 router
│   └── NNN-*.md             ← Architecture decisions
├── specs/
│   ├── README.md            ← L2 router
│   └── YYYY-MM-DD-*.md      ← Feature design specs
├── plans/
│   ├── README.md            ← L2 router
│   └── YYYY-MM-DD-*.md      ← Implementation plans
└── personal/                ← Personal notes (not loaded by Claude)
```

## Document types and line limits

| Type | Purpose | Line limit |
|------|---------|-----------|
| router | Navigation only — links, no content | 100 |
| runbook | Step-by-step procedures | 200 |
| reference | Stable lookup information | 300 |
| plan | Proposed approach with decisions | Unlimited |

Every markdown file must have YAML frontmatter:
```yaml
---
type: router|runbook|reference|plan
last_verified: YYYY-MM-DD
owner: your-name
---
```

## What goes where

| Content type | Location |
|---|---|
| Company background, teams, vocabulary | [`docs/context/taleemabad.md`](context/taleemabad.md) |
| Architecture decisions + rationale | [`docs/adr/`](adr/README.md) |
| Feature design / requirements | [`docs/specs/`](specs/README.md) |
| Step-by-step implementation plans | [`docs/plans/`](plans/README.md) |
| Dev commands, environment | [`docs/commands.md`](commands.md) |
| Code conventions, gotchas | [`docs/conventions.md`](conventions.md) |
| Design tokens, typography | [`docs/design-system.md`](design-system.md) |
| Personal notes, cheat sheets | [`docs/personal/`](personal/) |

## Personal notes (`docs/personal/`)

For human reading only — not referenced by CLAUDE.md. Use judgment:
- **Dedicated file** — topic is substantial (primer, detailed cheat sheet, decision with context)
- **Append to `notes.md`** — short miscellaneous items

## Work tracking (beads)

Active work lives in [`.beads/`](../.beads/README.md), not in docs. Open a bead before starting any non-trivial task.
