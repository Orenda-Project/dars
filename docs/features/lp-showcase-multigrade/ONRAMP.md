# Onramp — LP Showcase Multi-Grade

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

## Step 1 — Read these files, in this exact order

1. `dars/CLAUDE.md` (project root operating manual)
2. `docs/features/lp-showcase-multigrade/README.md`
3. `docs/features/lp-showcase-multigrade/01-decision-log.md` ← **load-bearing; frozen**
4. `docs/features/lp-showcase-multigrade/03-phase-1-multigrade-showcase.md` (only phase)
5. `docs/features/lp-showcase-multigrade/04-reference-lp-assistant-multigrade.md` (frozen LP Assistant contract — verified against `UG_LessonPlan` `main@4ec7b1d` on 2026-05-21)

Skim these for context (don't re-derive what they say):
- `useful-scripts/generate_showcase_lps.py` — the script you'll be extending
- `webapp/components/templates/showcase-template.tsx` — the page you'll be widening
- `webapp/app/showcase/[tag]/page.tsx` — the loader (typically only type changes here)
- `webapp/public/showcase/lp-showcase/index.json` — the current 10-entry single-grade index (what you're appending to)

## Step 2 — Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. phase doc                  (specs derived from decisions)
3. reference doc              (external API shape, frozen)
4. running code               (last; code may be stale)
```

If two docs disagree, this is the order. Code is **lowest** authority. Surface conflicts; don't silently pick a side.

## Step 3 — Who you are in this conversation

- Implement the single phase as one PR. One bead.
- PR targets `staging`. **NEVER `main`.**
- After merge, watch BOTH deploys (Railway server + Vercel webapp).
- Treat the decision log as frozen. To revise: ask the user, then add a `D-N+1` superseding entry. Both stay.
- Default mode is autonomous — don't pause to confirm understanding.

## Step 4 — Conversational style (verbatim)

- No pre-action narration ("I'll now do X"). Do it, then report.
- One design question at a time via `AskUserQuestion` with 2–4 options + a Recommended.
- Use sub-agents for exploration (>3 search queries); synthesise yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing it if you edited it earlier this session.

## Step 5 — Current state

| Phase | Status | PR | Notes |
|---|---|---|---|
| Phase 1 — Multi-grade LPs in the showcase | 🟡 In flight | (pending) | F-1.1 → F-1.5 implemented on branch `feat/lp-showcase-multigrade`. Regenerated showcase: 13 entries (10 single-grade with reviews, 3 multi-grade rendered via the new Python renderer per D-7). Awaiting commit + PR. |

**Next thing to do:** commit the changes on `feat/lp-showcase-multigrade`, push, and open a PR against `staging`. After merge, watch Railway (server) — skipped if no server files changed — and Vercel (webapp). Update Step 5 with PR number and mark ✅ when both deploys are green.

## Step 6 — Where to find supporting context

- Sibling repo for the LP Assistant API: `/home/hataf/taleemabad/UG_LessonPlan/` — pulled latest at `4ec7b1d` on 2026-05-21. Source of truth for the multigrade contract is `main.py` (lines ~2932–3058) + `utils/webhook_utils.py` (`RedisCache`) + `config.py` (`VALID_CURRICULUMS`).
- Bead tracker: `.beads/status.jsonl` (append-only)
- Graphify report (read for architecture questions): `graphify-out/GRAPH_REPORT.md`
- Existing showcase generator: `useful-scripts/generate_showcase_lps.py`
- Existing showcase frontend: `webapp/components/templates/showcase-template.tsx` and `webapp/app/showcase/[tag]/page.tsx`

## Step 7 — Things to ask the user before acting

- **`LP_ASSISTANT_API_KEY`** — required for F-1.5 (regeneration). The script reads it from env.
- **Multi-grade specs** — D-2 names three candidate specs (G2–G3 Reading, G4–G5 Comprehension Q&A, optional G1–G5 Creative Writing). If LP Assistant rejects any (e.g. unsupported page numbers for a given grade), surface the failure and ask whether to substitute or drop that spec.
- **Regeneration cost** — the script `reset_output_dir`s and regenerates all 10 single-grade LPs plus the new multi-grade entries. User has accepted this cost trade-off before, but flag if running outside a normal showcase refresh.
- **Anything not covered by the decision log** — pause and use `AskUserQuestion`.

## Step 8 — How to start this phase as a fresh agent

1. Read everything in Step 1.
2. `git fetch origin && git checkout -b feat/lp-showcase-multigrade origin/staging`.
3. Append the bead `feat-lp-showcase-multigrade-phase-1` to `.beads/status.jsonl` with `status: "in_progress"`.
4. Implement F-1.1 (widen `LPSpec.grade` + `index.json` shape + `wrap_html` heading).
5. Implement F-1.2 (`generate_one_multigrade()` + polling per the reference doc — note `data.response.lesson_plan`, not `data.lesson_plan`).
6. Implement F-1.3 (skip review for list-grade entries in `write_results()` and `run_reviews()`).
7. Implement F-1.4 (frontend: widen `ShowcaseEntry.grade`, bucket multi-grade into a "Multi-Grade" sidebar group, render "Grades X–Y · Skill" in the main-pane header).
8. Implement F-1.5 (append 2–3 multi-grade `LPSpec` entries; run the script to regenerate; commit the resulting HTML + updated `index.json`).
9. Update Step 5 Current State (mark Phase 1 ✅, name the PR number).
10. Commit, push, open PR against `staging`. After merge: watch Railway + Vercel deploys.
11. Close the bead.

## Step 9 — Keep the plan files alive (HARD RULE)

| When you… | Update… |
|---|---|
| Land the PR on staging | Mark Phase 1 ✅ in Step 5 of this onramp + add PR # |
| Make a decision the plan didn't anticipate | Add `D-N` to `01-decision-log.md` (rationale + when) |
| Supersede an old decision | Amend old: "Superseded by D-N+1 on YYYY-MM-DD"; new references the supersession. Both stay. |
| Find LP Assistant has drifted from the reference doc | Update `04-reference-lp-assistant-multigrade.md` in the same PR; bump the verified commit in D-3 |
| Hit a real-world snag in execution (e.g. a spec fails) | Append to phase doc `## Notes from execution` |

### Self-check before closing the bead

- [ ] `webapp/public/showcase/lp-showcase/index.json` contains 2–3 entries with `grade` as a list.
- [ ] The `/showcase/lp-showcase` page renders three sidebar groups: Grade 2, Grade 5, Multi-Grade.
- [ ] Selecting a multi-grade entry shows "Grades X–Y · Skill" in the main-pane header and no review drawer.
- [ ] Single-grade entries still render exactly as before (review drawer when enabled).
- [ ] Step 5 of this onramp is updated with the merged PR number.
- [ ] Railway + Vercel both show SUCCESS on the merge commit.
- [ ] `docs/features/README.md` index moved this feature into the Closed section.

If any check fails, fix before closing.
