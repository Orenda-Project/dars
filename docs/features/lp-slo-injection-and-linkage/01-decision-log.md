# Decision Log — LP ↔ Sub-SLO injection and linkage

Decisions are frozen once shipped. To revise a frozen decision: mark the old "Superseded by D-N+1 on YYYY-MM-DD"; the new one references the supersession.

---

**D-1: `custom_prompt` is the steering channel.** When dispatching to LP Assistant v3, populate the `custom_prompt` field with a sub-SLO coverage instruction. The exact string is:

```
After this lesson plan, the following sub-SLOs should be covered:
- <sub_slo.statement>
- <sub_slo.statement>
...
```

*Rationale:* The user explicitly requested this format. LP Assistant v3 accepts `custom_prompt` and appends it to the base prompt; no LP Assistant change needed. Using `statement` (not `code`) keeps the LLM grounded on meaning rather than opaque identifiers.

*Apply:* `dars/generated_lps/lp_assistant_client.py` `_build_body`; only attach when the caller passes a non-empty list. The v2 rebuild plan at `docs/plans/2026-05-15-dars-v2-rebuild/05-phase-3-generation-pipeline.md` line "Do NOT send `custom_prompt`" is superseded by this decision for the sub-SLO-injection path — note the supersession in the same PR.

*Decided:* This feature.

---

**D-2: Persist *requested* sub-SLOs at insert time, separately from *covered*.** Add a new column `requested_sub_slo_ids UUID[]` to `generated_lps`, set on the initial PENDING insert (and never changed afterwards). The existing `covered_sub_slo_ids` continues to be populated by F3.8 after the LP returns.

*Rationale:* Two distinct concepts: (a) "this LP is **for** these sub-SLOs" (intent, set at request time, used for filtering and reporting), and (b) "this LP **evidenced** these sub-SLOs" (post-hoc analysis). Conflating them loses information — an LP that's still PENDING has known intent but no evidence yet. Coverage analytics (Phase 5 SLO coverage dashboard) should be able to count both.

*Apply:* migration adds the column; service insert path sets it; webhook + tagging path leaves it alone.

*Decided:* This feature.

---

**D-3: Source the sub-SLO set deterministically from `topic_sub_slos`.** For a lesson slot with `topic_id = T`, the requested sub-SLO set is exactly `SELECT sub_slo_id FROM topic_sub_slos WHERE topic_id = T` (ordered by `sub_slos.code` for stability). No LLM, no derived rule — pure join.

*Rationale:* `topic_sub_slos` is already the canonical mapping (set in the seed and curatable later). Re-deriving via LLM would introduce drift between what the curriculum team owns and what the generator sees. Sorting by `code` makes the `custom_prompt` string deterministic for cache-key purposes (see D-6).

*Apply:* new helper `_load_topic_sub_slos(conn, topic_id)` in `dars/generated_lps/service.py`; revision path uses the union helper (D-5).

*Decided:* This feature.

---

**D-4: Empty sub-SLO set is allowed — no `custom_prompt` sent.** If a topic has zero rows in `topic_sub_slos`, dispatch without `custom_prompt` (back to today's behavior). Don't fail, don't log warning above INFO. Set `requested_sub_slo_ids = []` on the row.

*Rationale:* Topics added by teachers as custom slots (D-57 of the v2 rebuild) might not have sub-SLO mappings yet. Failing closed would block LP generation for those slots, which violates the "errors don't block teaching" principle (F3.13 / D-50 of the v2 rebuild).

*Apply:* `_build_body` only adds `custom_prompt` to the dict when the list is non-empty. Empty list still produces a valid v3 request.

*Decided:* This feature.

---

**D-5: Revision LPs request the union of prior topics' sub-SLOs.** For a revision slot, `requested_sub_slo_ids = union(topic_sub_slos.sub_slo_id) ∀ topic ∈ prior_topics_after_cap`. The cap is `REVISION_MAX_PRIOR_TOPICS` (already 5 in `service.py`) — same cap as the page_content concatenation, so the steering set matches the content set.

*Rationale:* Symmetry with F3.8's existing candidate-union logic for revision LPs lets `requested` and `covered` be compared apples-to-apples. Using the *capped* set (not all prior topics) keeps steering aligned with what was actually sent in `page_content`.

*Apply:* `get_or_generate_revision_lp` computes the union via a `WHERE topic_id = ANY($1)` query against `topic_sub_slos` after the cap is applied.

*Decided:* This feature.

---

**D-6: Cache key does NOT change.** The cache key remains `f"{curriculum_id}:{topic_id}:{lp_type}"` (global) or `f"{curriculum_id}:{cst_id}:{topic_id}:{lp_type}"` (class). Sub-SLO membership is a deterministic function of `topic_id`, so including the sub-SLO set in the cache key would just add a redundant hash.

*Rationale:* If the curriculum team edits `topic_sub_slos` for an existing topic, the *current* requested set drifts from the set that produced any already-cached LP. We accept that drift in v1 — invalidating cached LPs on `topic_sub_slos` changes is a separate operational concern (Phase 5 SLO-edit flow). v1 stance: cached LP wins; `requested_sub_slo_ids` is a snapshot of intent at the time of dispatch and may be stale relative to current `topic_sub_slos`. This is acceptable because (a) the v1 seed is frozen, and (b) consumers should treat the column as "intent at generation time" rather than "current intent."

*Apply:* leave cache_key builders alone. Add a one-line comment in `_build_cache_key_global` noting that requested_sub_slo_ids is intentionally outside the key.

*Decided:* This feature.

---

**D-7: One migration, append-only — column with NULL default.** The migration adds `requested_sub_slo_ids UUID[] NULL DEFAULT NULL`. Existing rows stay NULL (we don't backfill from `topic_sub_slos`).

*Rationale:* Backfilling would write "intent" we didn't actually communicate to LP Assistant for those rows. Misleading. NULL is the honest record for pre-feature LPs. New rows always get an array (empty if D-4 applies).

*Apply:* new migration file under `server/src/dars/migrations/`. Naming follows the existing pattern (timestamp prefix). Migration runs on Railway deploy per CLAUDE.md rule #7.

*Decided:* This feature.

---

**D-8: F3.8 candidate set is unchanged.** The existing post-generation tagging continues to receive the topic's current sub-SLOs as candidates (not the snapshot in `requested_sub_slo_ids`). This keeps F3.8 evidence-based against the curriculum team's *current* truth.

*Rationale:* If we passed `requested_sub_slo_ids` to F3.8, a stale snapshot would lock the tagging analysis to outdated candidates. Keeping F3.8 sourced from the live join means tagging always reflects the curriculum's current state.

*Apply:* no change to `lp_tagging_service.tag_lp` or its caller. (The caller is whoever wires F3.8 into the webhook flow — search `tag_lp(` to confirm; if not yet wired, leave a TODO in the phase doc.)

*Decided:* This feature.
