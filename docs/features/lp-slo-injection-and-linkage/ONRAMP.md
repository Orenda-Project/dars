# Onramp — LP ↔ Sub-SLO Injection and Linkage

You are a Claude agent picking up an in-flight effort. This file is your single entry point. Reading it (and the files it lists) gives you the full context.

You will NOT execute any code, open beads, or write files until you have read everything this file lists.

---

## Step 1 — Read these files, in this exact order

1. `dars/CLAUDE.md` — project rules (rules 1–15 are critical; especially #2 never push to main, #7 migrations are file-only and applied on deploy, #11 structured logging, #12 autonomous default, #15 re-read before re-editing).
2. `docs/features/lp-slo-injection-and-linkage/README.md` — feature framing.
3. `docs/features/lp-slo-injection-and-linkage/00-glossary.md` — *Requested sub-SLOs*, *Custom prompt*, *Revision sub-SLO set*; contrast with *Covered sub-SLOs* (the existing F3.8 output).
4. `docs/features/lp-slo-injection-and-linkage/01-decision-log.md` — D-1..D-8. All settled. Don't re-derive.
5. `docs/features/lp-slo-injection-and-linkage/02-phase-1-injection-and-linkage.md` — the single execution phase. F1.1..F1.5.

Reference (read only when touching the code itself):
- `server/src/dars/generated_lps/lp_assistant_client.py` — the request builder; D-1 changes `_build_body`.
- `server/src/dars/generated_lps/service.py` — the three entry points threaded by F1.4 (`get_or_generate_lp`, `get_or_generate_class_specific_lp`, `get_or_generate_revision_lp`).
- `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` — the `generated_lps` table; F1.5 adds a row to this doc.
- `docs/plans/2026-05-15-dars-v2-rebuild/05-phase-3-generation-pipeline.md` — F3.2 spec; F1.5 adds the supersession note.

---

## Step 2 — Document precedence

```
1. 01-decision-log.md                                       (D-N references are canonical for this feature)
2. ../../plans/2026-05-15-dars-v2-rebuild/02-data-model.md  (schema ground truth; this feature appends one row)
3. 00-glossary.md                                           (terminology specific to this feature)
4. 02-phase-1-injection-and-linkage.md                      (specs derived from above)
5. running code                                             (last; code may be stale)
```

If two docs disagree, this is the order. Surface conflicts; don't silently pick a side.

---

## Step 3 — Who you are in this conversation

- Implement F1.1..F1.5 in order. One bead.
- PR targets the staging branch (`feat/webhooks-async-lp` is the current parking branch per repo state at handoff; verify with `git branch -vv` before branching). NEVER `main`.
- After merge, watch Railway server deploy (no webapp changes in this feature).
- Treat D-1..D-8 as frozen. To revise, ask the user; if approved, mark old "Superseded by D-N+1 on YYYY-MM-DD" and add the new entry. Don't overwrite.

---

## Step 4 — Conversational style (verbatim)

- Default mode: autonomous. Don't pause to confirm understanding.
- No pre-action narration ("I'll now do X").
- One design question at a time via AskUserQuestion with 2–4 options + a Recommended pick.
- Use sub-agents for exploration (>3 search queries); synthesize yourself.
- Commit + push + open PR is ONE flow.
- After merge, watch deploys (don't wait to be asked).
- Re-read a file before editing if you edited it earlier this session.

---

## Step 5 — Current state

**As of 2026-05-20 — single PR in flight: F1.1..F1.5 bundled.**

| Item | Status |
|---|---|
| Plan written | ✅ README + glossary + decision log + phase doc + features index |
| Plan reviewed by user | ✅ approved on 2026-05-20 |
| F1.1 Migration | ✅ `20260520000001_generated_lps_requested_sub_slos.sql` |
| F1.2 Topic→sub-SLO loader | ✅ `_load_topic_sub_slos` + `_load_union_topic_sub_slos` |
| F1.3 `custom_prompt` in request body | ✅ `LPRequest.sub_slo_statements` + `_build_custom_prompt` |
| F1.4 Thread requested set through 3 entry points | ✅ global / class / revision |
| F1.5 Tests + plan cross-references | ✅ 3 new client tests + 1 DB-gated service test; F3.2 spec marked superseded; data-model row added |
| Staging deployed | 🟡 awaiting Railway after merge |
| Bead `feat-lp-slo-injection-and-linkage` | 🟡 open; close after staging green |

**Next thing to do unless the user says otherwise:** wait for the PR to merge, watch Railway server deploy on the parking branch, confirm `requested_sub_slo_ids` populates on a fresh dispatch via the demo API key, then close the bead and move this feature to Closed in `docs/features/README.md`.

---

## Step 6 — Where to find supporting context

| If you need… | Look here |
|---|---|
| LP Assistant client + builder | `server/src/dars/generated_lps/lp_assistant_client.py` |
| Three service entry points | `server/src/dars/generated_lps/service.py` |
| Existing tagging service (don't touch — D-8) | `server/src/dars/breakdown/lp_tagging_service.py` |
| Migrations dir (where F1.1 file goes) | `server/src/dars/migrations/` |
| Existing tests pattern | `server/tests/` (search `test_lp_assistant_client` and `test_generated_lps_service`) |
| topic_sub_slos table definition | `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` §3 |
| v2 rebuild plan (cross-ref target) | `docs/plans/2026-05-15-dars-v2-rebuild/` |
| Bead file | `.beads/status.jsonl` |
| User preferences | `~/.claude/projects/-home-hataf-taleemabad-dars/memory/` |

---

## Step 7 — Things to ask the user before acting

- Anything that would change `topic_sub_slos` data (this feature reads it; doesn't write it)
- Production deployment (default: no)
- Skipping any of F1.1..F1.5 (the migration must ship with the code)
- Changing the D-1 `custom_prompt` string (user signed off on this format)

For everything else: act autonomously.

---

## Step 8 — How to start the phase as a fresh agent

1. Re-read this file end to end.
2. Read the phase doc end to end.
3. Open bead `feat-lp-slo-injection-and-linkage` by appending to `.beads/status.jsonl`.
4. Branch from the current staging parking branch (verify with `git branch -vv` first; current is `feat/webhooks-async-lp` at handoff).
5. Implement F1.1..F1.5 in order. Bundle into one PR (S-sized feature).
6. Run the server test suite locally.
7. Commit + push + open PR against the parking branch.
8. After merge, watch Railway server deploy; then update Step 5 Current state ✅ and close the bead.

---

## Step 9 — Keep the plan files alive (HARD RULE)

- **In the same PR that lands the feature**, update:
  - `docs/plans/2026-05-15-dars-v2-rebuild/05-phase-3-generation-pipeline.md` F3.2 — add the D-1 supersession note (per F1.5 spec)
  - `docs/plans/2026-05-15-dars-v2-rebuild/02-data-model.md` `generated_lps` table — add the `requested_sub_slo_ids` row
  - This file's **Step 5 — Current state** — mark phases ✅ as they complete
  - `docs/features/README.md` — when the feature ships, move it from Active to Closed
- **If you discover a new design decision** mid-execution: add a new `D-N` entry to `01-decision-log.md`. If it conflicts with an existing decision, surface to user first, then mark the old "Superseded".
- **Don't reformat unrelated parts of plan files.** Diffs should be substantive.

### Self-check before closing the bead

- [ ] Migration applied on staging (Railway deploy SUCCESS)
- [ ] All three service entry points wired
- [ ] Body builder sends `custom_prompt` when sub-SLOs exist; nothing when empty
- [ ] Tests pass
- [ ] v2 rebuild plan docs cross-referenced
- [ ] Step 5 Current state in this file ✅
- [ ] `docs/features/README.md` moves this feature to Closed
- [ ] A fresh agent reading this file knows the feature is done

If any check fails, fix before closing.
