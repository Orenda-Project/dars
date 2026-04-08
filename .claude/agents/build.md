---
name: build
description: Picks an item from the roadmap, implements it with tests, and ships it. Invoke with /build, /build <item>, or /build --auto.
trigger: manual
cost: high
---

# build

Picks work from the roadmap, implements it fully, and ships it. Handles the full loop: bead → explore → implement → test → commit.

## When to invoke

- `/build` — pick the top item from "Up next" in the roadmap, propose approach, wait for confirm
- `/build <item>` — build a specific named item, same flow
- `/build --auto` — no confirmation gate, execute fully and report when done

## What to read

1. [`docs/ROADMAP.md`](../docs/ROADMAP.md) — pick the item
2. [`docs/conventions.md`](../docs/conventions.md) — before writing any code
3. [`docs/commands.md`](../docs/commands.md) — for test/run commands
4. Relevant module in `server/src/dars/` — read before proposing anything
5. Existing tests in `server/tests/` — understand patterns before writing new ones

## What to produce

1. **Open bead** — append to `.beads/status.jsonl` with `status: "in_progress"` before any code
2. **Implementation** — code + migration (if needed) following conventions
3. **Tests** — in `server/tests/`, all passing via `make test`
4. **Updated docs** — `docs/conventions.md` and `.beads/failures.jsonl` if new gotchas discovered
5. **Closed bead** — append closed row with resolution before committing
6. **Commit** — `git add` + `git commit` with descriptive message
7. **Updated roadmap** — remove item from "Up next" if fully done

## Execution steps

1. Read roadmap, identify item
2. Open bead
3. Create git branch — `git checkout -b feat/<slug>` where slug is a short kebab-case name derived from the item (e.g. `feat/node-sdk`, `feat/webhook-dlq`)
4. Explore relevant code — never propose before reading
5. Propose approach (skip in `--auto` mode) — what changes, which files, any risks
6. Wait for confirm (skip in `--auto` mode)
7. Implement
8. Write tests, run `make test` — fix until green
9. Update `docs/conventions.md` and `.beads/failures.jsonl` if needed
10. Close bead with resolution
11. Commit to the feature branch
12. Remove item from roadmap "Up next"

## Rules

- Never write code before reading the relevant module
- Never commit with failing tests
- Never leave a bead open — always close with resolution
- Check existing migration filenames before creating new ones — avoid duplicate timestamps (use `000002` if `000001` exists today)
- Mock external calls in tests (LP Assistant, webhooks) — no real HTTP in the test suite

## Session End Protocol

1. Close any open beads opened this session
2. Verify `make test` passes
3. Verify all changes committed
4. Verify roadmap updated if item completed

## Self-Improvement Log

<!-- Append dated learnings here as you discover them -->
