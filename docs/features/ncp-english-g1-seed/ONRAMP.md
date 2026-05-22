# Onramp — for the NCP English G1 Seed work

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context the originating Claude had.

**You will NOT execute any code, open beads, or write files until you have read everything this file lists.** After reading you are expected to either resume execution at the current state or ask the user ONE focused question. You are NOT expected to re-derive any decision in the decision log — those are settled.

---

## Step 1 — Read these files, in this exact order

1. **`dars/CLAUDE.md`** — project rules. Critical: rules 1–15.
2. **`docs/features/ncp-english-g1-seed/README.md`** — index and scope summary.
3. **`docs/features/ncp-english-g1-seed/00-glossary.md`** — NCP-specific terms.
4. **`docs/features/ncp-english-g1-seed/01-decision-log.md`** — D-1..D-17, with two supersessions (D-2 → D-11, D-10 → D-12). This is the load-bearing file. **Re-read in full whenever you arrive cold.**
5. **`docs/features/ncp-english-g1-seed/02-data-sources.md`** — per-layer mapping from upstream source → Dars target table.
6. **`docs/features/ncp-english-g1-seed/03-phase-1.md`** — the sole phase doc, 9 features F1.1..F1.9.
7. **`docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md`** — the v2 schema; F1.1's migration updates §sub_slos there.
8. Sibling repo references (only when relevant):
   - `taleemabad-core/taleemabad_core/apps/slo/` for NCPSLO model shape
   - `Schema/services/slo_mapping.py` + `Schema/services/chapter_plan.py` for sub-SLO breakdown and topic↔sub-SLO mapping
   - `UG_LessonPlan/` only if you start touching LP generation (this feature does not)

Skim, don't memorize. Come back to the plan as needed.

---

## Step 2 — Document precedence (if two docs disagree)

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-sources.md         (extraction approach is ground truth)
3. 00-glossary.md             (terminology)
4. phase docs (03, 04)        (specs derived from above)
5. running code               (last; code may be stale)
```

Code is **lowest** authority. Surface conflicts; don't silently pick a side. If a conflict involves the v2 rebuild's `02-data-model.md`, that doc wins over this feature's docs for schema questions.

---

## Step 3 — Who you are in this conversation

- **Implement phases sequentially.** One bead per phase. Open when starting, close when staging is green.
- **PRs target `staging`. NEVER `main`.** Rebuild rule + memory `feedback_never_touch_main_prod`.
- **After every merge to staging, watch BOTH Railway services** (`dars` + `truthful-renewal`). Memory `feedback_deployment_watch_both`.
- **Treat the decision log as frozen.** If you think a decision is wrong, raise it with the user; don't silently revise.

---

## Step 4 — Conversational style

### Default mode: autonomous
Don't pause to confirm understanding. Proceed. User redirects if needed. Only exception: genuine blocker (missing spec, missing credential, ambiguity in a decision).

### No pre-action narration
Never write "I'll now do X". Do X, then state the result.

### One question at a time for design Q&A
When you genuinely need user input on a design call, use `AskUserQuestion` with 2–4 options. Mark a Recommended pick. Wait for the answer. Then the next question.

### Use sub-agents for exploration; do the synthesis yourself
Broad codebase questions (>3 search queries) → Explore agent. Synthesise yourself.

### Commit + push + open PR is one flow
When work is done: commit (with Co-Authored-By footer), push, open PR against `staging`. Memory `feedback_commit_push_pr_flow`.

### After merge, watch deploys
Don't wait to be asked. Use `mcp__Railway__list-deployments` on both services.

### Re-read before editing
If you wrote a file earlier in the session and want to edit it now, re-read it first.

### Reaction phrases
When something works, say "gg" naturally. When it breaks, "chammaar." Memories `feedback_gg`, `feedback_chammaar`.

---

## Step 5 — Current state

**As of 2026-05-22 — Phase 1 complete. NCP English G1 data is live on Dars staging.**

| Feature | Status |
|---|---|
| F1.1 — Migration: `sub_slos.recommended_lp_type` | ✅ shipped via PR #87, applied on staging |
| F1.2 — `lp_type_heuristics` + `auto_build_service` sub-SLO precedence | ✅ 6 new tests pass; 18/18 total |
| F1.3 — Script scaffold + dual DB connections | ✅ `scripts/import_ncp_english_g1.py` |
| F1.4 — Claude lp_type classifier | ✅ `scripts/lp_type_classifier.py`; 6 mocked tests pass |
| F1.5 — Upsert NCP curriculum + SLOs | ✅ live: 91 NCP English G1 SLOs on staging |
| F1.6 — Sub-SLO breakdown via Anthropic + Claude lp_type | ✅ live: 11 sub-SLOs (sparse — see D-22); D-21 streaming patch |
| F1.7 — Book 1171 + chapters upsert (book.book_text slicing) | ✅ live: 8 chapters (4 soft-deleted in fde_staging) |
| F1.8 — Topics + topic↔sub-SLO via Anthropic mapper | ✅ live: 8 synthetic topics + 27 topic↔sub-SLO mappings |
| F1.9 — Run on staging, delete `import_books.py`, open PR | ✅ PR #87 merged 2026-05-21; script run 2026-05-22 |

**End-to-end verification (2026-05-22):**
- Sample NCP org (`4ab011dd-d081-4654-a72a-52dcc84a92d3`) signed up on staging with `curriculum_code=NCP`.
- `POST /api/v2/breakdowns/auto-build` produced a draft org-scope breakdown (`c4dcbf75-4016-4156-af56-55539fe8b0ce`): 8 chapters · 139 lessons · 25 FA · 8 SA · 8 revision = **180 slots** (D-74 invariant holds).
- Total Anthropic spend for the import run: ~$0.93 (one Opus breakdown + 11 Haiku lp_type classifies + 8 Opus topic-mapper calls).

**Out-of-scope incident, fixed mid-session:** unrelated 500 in `POST /api/v1/academic-years` (`AcademicYearCreate.start_date` was typed `str` instead of `datetime.date`). Fixed in PR #90, deployed staging 2026-05-22; UI-verified.

**Next thing to do unless the user says otherwise:**

Phase 1 is done. There is no Phase 2 in this feature (D-18). Likely follow-ups (NOT part of this feature):
- Richer sub-SLO breakdown: replace the single bulk Opus call with per-SLO calls if 11 sub-SLOs / 91 SLOs is too thin for downstream LP generation quality (D-22).
- Restore the 4 soft-deleted chapters if content team confirms they should be live.
- Repeat the seed for another grade/subject cell (NCP × G2, NCP × Urdu, etc.) — D-1 scopes this feature to one cell only.

---

## Step 6 — Where to find supporting context

| If you need… | Look here |
|---|---|
| Live `fde_staging` schema (read-only) | Postgres at `CORE_STAGING_DB_*` env vars in `dars/.env` (D-17) |
| Live Dars staging DB (read-write target) | `DARS_STAGING_DATABASE_URL` in `dars/.env` (D-19) — user adds this before running the script |
| NCPSLO Django model (for reference, not import) | `taleemabad-core/taleemabad_core/apps/slo/models.py` |
| Schema's breakdown service | `Schema/services/slo_mapping.py::get_sub_ncp_slos_for_mapping` |
| Schema's topic-to-SLO mapper | `Schema/services/chapter_plan.py::map_topics_to_ncp_slos` |
| Existing Dars seed (for shape reference) | `server/src/dars/seeds/slos_dars_english_g1.py`, `server/src/dars/seeds/dars_english_g1_book/` |
| v2 schema canonical doc | `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` |
| Active beads | `.beads/status.jsonl` |
| User memory + preferences | `~/.claude/projects/-home-hataf-taleemabad-dars/memory/` |

If any path has moved, ask before guessing.

---

## Step 7 — Things to ask the user about before acting

Most decisions are settled. Ask if these come up:

- **Production deployment of anything.** Default no.
- **Schema/data-model changes not in 01-decision-log.md.** Only D-12 (`sub_slos.recommended_lp_type`) is approved. Anything else → ask.
- **A different book id** (other than 1171) for this feature. The script accepts `--book-id` but this feature is scoped to 1171 (D-15). Other books are out-of-scope for the close-out PR.
- **Re-running Schema breakdown** after it's been run once. Idempotent re-runs are fine (script just upserts again), but if you suspect the breakdown content has drifted → confirm with user before overwriting.
- **Re-running the Claude lp_type classifier** to overwrite assigned values. Same.
- **Running the script against production** (anything other than Dars staging). Default no.
- **A decision in the log that feels wrong.** Surface it; propose a fix; don't act unilaterally.

For everything else: act autonomously, report results.

---

## Step 8 — How to start a phase as a fresh agent

1. Read this file end to end (or re-skim if recent).
2. Read the phase doc (`03-phase-1-extract-fixtures.md` for Phase 1).
3. Open the phase's bead via `bd open ...` per `.beads/README.md`. Bead id: `feat-ncp-english-g1-seed-phase-{N}-{slug}`.
4. Branch from `staging` (NEVER main): `git fetch origin staging && git checkout -b feat/ncp-english-g1-seed-phase-{N} origin/staging`.
5. Implement features in order (F-N.1 → F-N.K). Each feature has a Spec + Acceptance + Dependencies in the phase doc.
6. When the phase's last feature lands and staging is green: update **Step 5 Current state** in this file, close the bead, open the next phase's bead if proceeding.

If step 1–6 doesn't make sense given the user's instruction, ask one question. Don't guess.

---

## Step 9 — Keep the plan files alive (HARD RULE)

This is what makes the work survive across sessions. Treat it like "never push to main".

### What to update, and when

**After every feature lands on staging:**
- Update **Step 5 Current state** in this file. Reflect the new feature in the phase row. If you completed the phase's last feature, mark the phase ✅ and update "Next thing to do".

**When a phase completes:**
- Mark the phase ✅ here
- Close the bead
- If there are follow-ups, append to the phase doc under `## Notes from execution` (do NOT alter original spec sections)

**When you make a decision the plan didn't anticipate:**
- Add a new `D-N` entry to `01-decision-log.md`. Include rationale, who decided, when.
- If it conflicts with an existing decision: surface to user; do not override unilaterally. Once approved, mark the old "Superseded by D-N+1 on YYYY-MM-DD", and reference the supersession in the new entry. Both stay.

**When you change the data model:**
- Update `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` in the same PR as the migration SQL.

**When you introduce a new term:**
- Add it to `00-glossary.md`.

**When you change scope mid-feature:**
- Revise the feature's Spec + Acceptance in the phase doc, with an inline "Scope change YYYY-MM-DD" note.

### What NOT to do

- Don't rewrite history. Superseded decisions stay.
- Don't truncate the decision log. It grows.
- Don't reformat plan files you don't need to change.

### Self-check before closing a phase's bead

- [ ] Step 5 Current state reflects new completed state
- [ ] Phase doc has no stale specs (scope changes documented inline)
- [ ] Any new decisions are in the decision log
- [ ] Any new terms are in the glossary
- [ ] `02-data-model.md` of the v2 rebuild matches the actual schema
- [ ] A fresh agent reading this onramp would correctly identify what to do next

If any check fails, fix before closing.
