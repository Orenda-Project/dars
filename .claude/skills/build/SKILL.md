---
name: build
description: Use when picking up and shipping work from the Dars roadmap — opens a bead, implements with tests, commits, and closes the bead.
user-invocable: true
---

# build

Pick an item from the roadmap, implement it fully, and ship it.

## Invocation

- `/build` — pick the top item from the roadmap, propose approach, wait for confirm, then execute
- `/build <item>` — build a specific item, same flow
- `/build --auto` — no confirmation gate, execute fully and report when done

## Steps (always in this order)

1. **Read the roadmap** — [`docs/ROADMAP.md`](../../docs/ROADMAP.md). If no item specified, pick the top item from "Up next".

2. **Open a bead** — append to [`.beads/status.jsonl`](../../.beads/status.jsonl) with `status: "in_progress"` before touching any code.

3. **Explore** — read the relevant code. Understand what exists before proposing anything. Check `server/src/dars/` for the affected module.

4. **Propose approach** — one short paragraph: what you'll build, what files change, any gotchas. *(Skip in `--auto` mode.)*

5. **Wait for confirm** — do not write any code until confirmed. *(Skip in `--auto` mode.)*

6. **Implement** — write the code. Follow conventions in [`docs/conventions.md`](../../docs/conventions.md).

7. **Write tests** — tests live in `server/tests/`. Mock external calls (LP Assistant, webhooks). Run `make test` — all must pass before proceeding.

8. **Update docs** — if conventions, gotchas, or failures were discovered, update [`docs/conventions.md`](../../docs/conventions.md) and [`.beads/failures.jsonl`](../../.beads/failures.jsonl).

9. **Close bead + commit** — append closed bead row with resolution, then `git add` and `git commit`.

10. **Update roadmap** — if item is fully done, remove it from "Up next" in [`docs/ROADMAP.md`](../../docs/ROADMAP.md).

## Rules

- Never open a bead without closing it — resolution field must say what was done and how to verify
- Never commit with failing tests
- Never skip the explore step — read before proposing
- If the item requires a DB migration, check existing migration filenames first to avoid duplicate timestamps (use `000002` suffix if `000001` already exists today)
- `curriculum` defaults to `"ICT"` until stored on the LP model — note this in implementation if relevant

## What counts as done

- Tests pass (`make test`)
- Bead closed with resolution
- Committed to git
- Roadmap updated
