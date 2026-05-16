# Decision Log

Every decision from the Q&A session of 2026-05-15. Reference these by **D-N** in phase documents. If a decision needs to change, edit it here first and propagate.

---

## Architecture (round 1)

**D-A1: SLO-centric data model.** SLOs are the unit of truth, not LPs. Mark-taught flips sub-SLOs; coverage reports query sub-SLOs. *Rationale:* user's explicit goal is "track if teachers taught the SLOs."

**D-A2: Drop SLOChapter; link SLOs directly to BookChapters; sub-SLOs link to Topics.** Cleaner than taleemabad-core's 3-level hierarchy. *Rationale:* user pushback "I don't see a use of taleemabad core's SLOChapter system."

**D-A3: Override = fork (not delta).** When an Org or Class forks a parent breakdown, they get a full copy that diverges forever. *Rationale:* predictable for low-tech users; no "surprise updates."

**D-A4: Sequence-only with anchors.** Slot dates are computed from sequence position projected onto teaching days. `anchor_date` (admin-only) is the override. No stored `scheduled_date` on slots. *Rationale:* drift is automatic; mid-year join + skip-day work naturally; admins can still pin final exam dates.

**D-A5: Plan vs progress split.** Plan is immutable BreakdownSlot rows; progress is the `SlotProgress` event log. *Rationale:* lets us answer "did the teacher actually teach Day 2 on April 8?"

**D-A6: Org → School → CST tenancy.** New entities. Org replaces `Client`. *Rationale:* user wants "admin manages multiple schools" model.

---

## Q&A (Q1–Q55)

**D-1: Survey UG_EG before plan-writing.** Done; the survey produced a precise spec that informed Decisions 39, 47.

**D-2: UG_EG accepts `page_content` on `origin/Staging` branch.** Plan assumes both LP Assistant and UG_EG accept caller-supplied content. *Verified:* commit on `Staging` of `/home/hataf/taleemabad/UG_EG` shows `page_content` field added in the same shape as LP Assistant.

**D-3: Eager sub-SLO breakdown during seed/import + manual trigger for ad-hoc.** *Rationale:* avoids surprise latency mid-flow; cacheable.

**D-4: Hybrid topic boundaries — Schema drafts, admin publishes.** For v1 seed, we hand-author. For future books, Schema runs and produces a draft; admin reviews. *Rationale:* best of LLM + human judgment.

**D-5: Mark-taught flips all sub-SLOs linked to the slot's topic.** v1 simplification; v2 may refine using LP tagging results. *Rationale:* tech-illiterate teachers; don't make them manage checklists.

**D-6: Assessments target topics, not sub-SLOs directly.** The exam payload is `page_content` built from the topics' `topic_text`. Sub-SLOs come along via Topic↔SubSLO links. FA = rolling window since last FA; SA = chapter; term-end SA = all chapters in term.

**D-7: Only admins (org level and above) can anchor.** Teachers can skip/insert; can't fix dates.

**D-8: Multi-class teachers have fully independent CST progress.** A teacher's classes can diverge in pace.

**D-9: Teacher app is auth-free (sample integration model).** Real teacher auth lives in the org's app, not in dars. Dars exposes API; orgs call with their API key + a teacher_id.

**D-10: Store per-generation cost from day one.** Persist `cost_usd` from LP Assistant / UG_EG metadata on generation rows.

**D-11: Out-of-order completion allowed.** Marking Day 3 without Day 2 leaves Day 2 as a visible gap. Sequence pointer = highest taught position + 1.

**D-12: Mid-year join is declarative ("I'm at Chapter 3, Day 5").** Sets sequence position directly. Pre-join slots are "unknown" coverage.

**D-13: One book per CST in v1.** Multi-book defers to v2.

**D-14: Chapter ordering: global default + org fork + class fork.** All three levels can reorder.

**D-15: Claude authors the v1 seed.** Believable Pakistani Grade 1 English content; SLOs, sub-SLOs, book, chapters, topics, breakdown.

**D-16: Execution order: backend foundation → seed → backend features → teacher app → dashboard.** Phases 1–5 in this plan.

**D-17: Dashboard auth = email/password for org admin.** Org's API key remains for SDK/teacher-app usage.

**D-18: Breakdown versioning is simple immutable records.** Each edit creates a new Breakdown row with `previous_version_id`. No automatic upstream pulls; forks stay where they are. *v2 may add* "show changes since fork" UI.

**D-19: Drop most existing tests; rebuild around the seed.** Seed = canonical integration fixture.

**D-20: Plan format = README + glossary + decision log + data model + one file per phase.** This file structure.

**D-21: Revision LP page_content = concatenated topic_text of all prior topics in this chapter.** Chapter-end revisions only in v1; mid-term and term-end deferred.

**D-22: Run LP tagging on every generated LP.** Adds ~$0.002 + 5–10s per LP. Stored as `covered_sub_slo_ids` metadata.

**D-23: Org-level breakdown applies to all schools in the org.** Schools cannot override; only classes (CSTs) can fork further.

**D-24: Curriculum is global; orgs pick which to use.** No per-org curriculum forks. Orgs cannot edit curriculum SLOs/books.

**D-25: One curriculum per org.** Multi-curriculum chains use multiple orgs.

**D-26: Holiday model = 3-level inheritance (Org → School → CST).** Each level can add or remove holidays.

**D-27: Timetable is per-CST only. Default Mon–Fri (0..4).** Auto-populated on CST creation. (Note: current code auto-populates Mon–Sat 0..5; change to Mon–Fri.)

**D-28: Chapter days = module suggests + admin overrides.** Both. Module proposes a draft; admin can accept or change per chapter.

**D-29: Per-chapter day count includes lessons + FAs + revisions.** Total chapter budget = total period count, not just lesson count.

**D-30: Assessment cadence = ~1 FA every 5 lessons + 1 SA at chapter end.** Configurable at curriculum level; admins can override in their fork.

**D-31: Class-level mastery only in v1.** No per-student records. No Student entity.

**D-32: Mastery input via teacher app per-question form.** Teacher enters "X out of N correct" per question; we roll up to per-sub-SLO mastery.

**D-33: Port Schema modules into `dars/server/src/dars/breakdown/` as needed.** Module-by-module, not all upfront.

**D-34: Drop staging DB; production untouched.** Production migration is a separate later effort.

**D-35: Full rewrite of webapp (`/teacher-app` and `/dashboard`).** Delete and rebuild. Existing webapp is scaffolding for patterns, then deleted.

**D-36: Keep existing aesthetic.** Amber primary, slate neutrals, Georgia serif for LP content. No visual redesign in v1.

**D-37: English UI; RTL for Urdu content.** No full i18n in v1.

**D-38: LP Assistant v3 (async webhook) for all LP generation.** No sync calls.

**D-39: UG_EG v2 (async webhook).** Already what dars uses; keep.

**D-40: Webhook + manual poll.** `callback_url` in each request + `/api/v1/generations/{id}/refresh` endpoint for manual sync.

**D-41: Webhook auth = shared secret in `X-Webhook-Secret` header.** Both services include; dars verifies.

**D-42: FastAPI BackgroundTasks for short jobs; no queue.** LP/Exam jobs delegate to LP Assistant/UG_EG which are async themselves. Schema-ports use BackgroundTasks.

**D-43: Webhook idempotency by job_id.** Second call is a no-op if status is already terminal.

**D-44: Structured logs only in v1.** No Sentry, no Prometheus, no APM.

**D-45: No rate limiting in v1.** Track usage; decide later.

**D-46: LPs cached at `(curriculum, topic, lp_type)`.** Global breakdown pre-generates all LPs. Org/Class forks reuse cached LPs for unchanged slots; only custom slots generate fresh.

**D-47: Exams cached at `(curriculum, [topic_ids], generation_type, question_config_hash)`.** Same caching philosophy as LPs.

**D-48: No regenerate-on-demand for teachers in v1.** Teachers see whatever the cache has.

**D-49: Dashboard shows live batch generation progress.** "Generating LPs: 12 of 60" with webhook-driven updates.

**D-50: Failed LP generation shows "LP unavailable — contact admin."** Teacher can still mark taught.

**D-51: Ship each phase to staging as it completes.** No big-bang launch.

**D-52: Phase 1 = data model + seed + read-only API.** No writes, no FE changes.

**D-53: Claude drives execution; user reviews PRs.**

**D-54: One bead per phase.** Plan file is the spec; bead is work-tracking.

**D-55: No further concerns; write the plan.**

---

## Decisions made during plan-writing (post-Q55)

**D-56: GeneratedLP keying — non-revision LPs key on `(curriculum_id, topic_id, lp_type)`; revision LPs key on a hash of `(curriculum_id, sorted_topic_ids, lp_type='revision')`.** Distinct because revisions span multiple topics.

**D-57: When a class fork modifies a slot's topic or lp_type, the generated LP becomes class-specific (not cached).** Stored on a `class_specific_generated_lps` table or just `generated_lps.scope='class', scope_ref=cst_id`. The cache key for class-scoped LPs adds the CST id.

**D-58: AssessmentSlot covers an ordered set of topics, not a single topic.** Stored as a junction table `assessment_slot_topics(assessment_slot_id, topic_id, position)`.

**D-59: BreakdownSlot.slot_type enum:** `lesson | formative_assessment | summative_assessment | revision`. (`revision` is a distinct slot_type, not an lp_type — though when generated, its LP has `lp_type='revision'`.)

**D-60: `cst_state` table tracks per-CST runtime state:** `cst_id PK`, `current_sequence_position int`, `last_marked_at timestamptz`, `joined_at_position int` (for mid-year tracking).

**D-61: Curriculum mapping for downstream services (LP Assistant + UG_EG):** Dars's `curriculums.code` maps to the downstream services' curriculum enum as follows for v1:

| Dars curriculum | LP Assistant `curriculum` | UG_EG `curriculum` |
|---|---|---|
| `DARS` (mock) | `ICT` | `ICT` |
| `NCP` | `ICT` | `ICT` |
| `SNC` | `Punjab` | `Punjab` |

Stored as a static dict in `dars/breakdown/curriculum_mapping.py`. When new curricula are added (Palestine, Tanzania), Shujaan adds support upstream first; the mapping table is updated in lockstep. If a curriculum has no mapping defined, generation requests fail fast with a clear error (do not silently default to ICT for unknown curricula).

---

## Decisions made during Phase 1 execution

**D-62: All v2 PKs are UUID (not BIGSERIAL+UUID dual pattern).** *Rationale:* legacy schema used `BIGSERIAL id PK + UUID uuid UNIQUE` which means two identity columns per row. The v2 plan specifies UUID PKs everywhere; we don't carry forward the dual pattern. CLAUDE.md rule #6 (use `sqlalchemy.types.Uuid` not `dialects.postgresql.UUID`) still applies. *Decided:* during PR #37 (F1.1 cutover); surfaced by Phase 2 eval that no D-N entry captured it.

**D-63: v1 migration files (pre-20260516) were deleted, not kept.** *Rationale:* the v2 cutover supersedes them entirely; keeping them around caused the post-cutover re-run bug fixed in PR #39. *Decided:* PR #39. Going forward, when a future cutover-style migration is needed, follow the same pattern (delete + rename to force re-run).

**D-64: Domain prefixes for Dars Curriculum × G1 × English SLOs are `R`/`V`/`C`/`G`/`W` only.** *Rationale:* listening (L) and speaking (S) domains were dropped in F1.3 because LP Assistant has no matching `lp_type` (D-61). Each remaining domain maps 1:1 to a valid LP Assistant `lp_type`. There is no `S1-*` or `L1-*` SLO code in v1. *Decided:* PR #40.

**D-65: Demo org API key is deterministic and committed in repo.** Value: `dk_demo_dars_eng_g1_2dc7e0b8408142fa`. Stored hashed in `organizations.api_key_hash`. *Rationale:* staging only; production never sees this seed. Deterministic key means the seed is fully idempotent and repo-readable for test fixtures. *Decided:* PR #42.

---

## Decisions surfaced during Phase 2 eval (2026-05-15, pre-execution)

**D-66: Phase 2 F2.4 admin auth uses `X-Admin-Token` header backed by env var `DARS_ADMIN_TOKEN`.** *Rationale:* F2.4 calls global breakdown CRUD "admin-only" but didn't specify the mechanism. Header (not query string) + env-var-backed secret is consistent with existing webhook secret pattern (D-41). Compared with `hmac.compare_digest` per Critical Rule #5. *Application:* missing header or wrong value → 403. *Apply:* F2.4 onward. If you have a stronger preference, raise it before implementing.

**D-67: `class_lesson_slots.status` and `class_assessment_slots.status` are materialized columns updated by F2.12's mark-taught flow (not computed views).** *Rationale:* the data model description called it "denormalized; computed view OK too." We pick materialized to keep simple equality filters (`WHERE status='planned'`) fast across `class_lesson_slots` without join overhead. F2.12 must update both `slot_progress` (event log, append-only) AND the slot's `status` column (denorm) inside one transaction. *Apply:* F2.12 onward.

**D-68: F2.5 auto-build picks lp_type from a topic-to-lp_type heuristic table, with LLM fallback only on ambiguity.** *Rationale:* "the LLM picks per topic" is too non-deterministic for a global breakdown that needs to be reviewable. Heuristic first: if a topic title or first 200 chars of `topic_text` contain known signals (e.g. "comprehension" / "answer the questions" → `comprehension_qa`; "spelling" / "write" / "letters" → `creative_writing`; "grammar" / "noun" / "verb" / "pronoun" → `grammar`; "vocabulary" / "word meanings" / "synonyms" → `comprehension_word_meanings`; default → `reading`), use that. Only fall back to LLM when no heuristic matches AND the topic looks ambiguous. *Application:* the heuristic table lives in `dars/breakdown/lp_type_heuristics.py`. *Apply:* F2.5 onward.

**D-69: `breakdowns.book_id` is required for ALL scopes (global, org, class) in v1.** *Rationale:* D-13 says one book per CST. Allowing global breakdowns without a book opens an edge case (which book do the slots resolve topics against?) that doesn't pay for itself. Make `book_id NOT NULL` at the application level (DB allows NULL; v2 enforces via service-layer validation). *Apply:* F2.4 onward.

**D-70: `class_lesson_slots.status` and `slot_progress` reconciliation rule on out-of-order taught.** *Rationale:* D-11 allows marking Day 3 before Day 2. The reconciliation: slot.status updates to `taught` ONLY for the specific slot the teacher marked. Day 2's `slot.status` remains `planned` (a gap, visible in reports). `cst_state.current_sequence_position` = `max(taught/skipped/completed position) + 1`. SubSLO coverage flips per D-5 only for the actually-marked slot's topic. *Apply:* F2.12 onward.

**D-71: Generation webhook secret env var name is `LP_ASSISTANT_WEBHOOK_SECRET` and `UG_EG_WEBHOOK_SECRET`.** *Rationale:* the data model's `webhook_events.source` enum has values `lp_assistant` and `ug_eg`; the env vars follow the same naming for clarity. Used in Phase 3 (F3.6). *Apply:* Phase 3 onward.

**D-72: When `/teacher-app/*` returns 404 on staging during Phases 1–3, that's expected, not a bug.** *Rationale:* PR #47 (F1.10) deleted the legacy v1 routes the webapp called. Phase 4 (D-35) rewrites the webapp against `/api/v2/*`. The intermediate 404 window is by design. *Apply:* anyone observing the webapp during the transition.
