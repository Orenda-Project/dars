# Dars product backlog

Running list of UX, UI, and behavior issues found while QA'ing staging. Each entry: what's wrong, why it matters, proposed fix. Triage status: 🟢 next up · 🟡 known, deferred · ⚪ open question.

Not to be confused with `.claude/improvements.md`, which captures harness/agent improvements, not product.

---

## Dashboard

### 🟡 Class-detail breakdown view (deferred)

When we drop class-scope from the breakdowns index, teachers/admins still need a way to inspect what a specific CST is following. Should land on the class detail page as a read-only summary ("this class follows org breakdown X; overrides shown here"). Not yet built; revisit after the slot-per-day model change so we're not building UI we'll throw away.

### 🟢 One slot = one teaching day (model change)

**Symptom:** A breakdown shows `total_teaching_days: 27` but the slot list shows 4 lessons + 2 assessments + 1 revision = 7 slots. Today's model is "1 slot = 1 curriculum activity that may span multiple days." The mental model is unclear and the UI is confusing.

**Decision:** **switch to 1 slot = 1 teaching day.** 27 teaching days → 27 slots. Each slot has its own `lp_type`, its own topic, and its own generated LP. Multi-day activities become consecutive identical-topic slots.

**Why:**
- Day-by-day teacher plan — no "you're 2/3 through this lesson" ambiguity.
- Mark-taught becomes per-day, matching how teachers actually work.
- The projector becomes trivial: slot N → date N (after holiday/weekend skip).
- `total_teaching_days` and `count(slots)` reconcile by definition.

**Explicit non-concerns (per user):** LP generation cost / caching is not a constraint. Generate freely. We can revisit caching later as an optimisation.

**Open questions to answer before implementation:**

1. **How does auto-build allocate days per topic?** Options:
   - Uniform split (e.g. 27 days ÷ 3 topics = 9 each)
   - Proportional to `topic_text` length / page count
   - New column on `topics` for `recommended_teaching_days` (admin/curator-set)
2. **Should consecutive same-topic slots share metadata or be totally independent?** E.g. "Day 1: reading, intro" → "Day 2: reading, comprehension" — currently lp_type doesn't capture day-within-topic nuance.
3. **Migration:** existing seeded breakdowns + realized class slots on staging need to be re-built. Probably easiest: re-seed from scratch once we ship the new auto-build.
4. **What replaces `total_teaching_days` on the breakdown row?** Probably drop (becomes redundant with count(slots)) — or keep as the admin-facing budget input that auto-build expands into N slots.

**Next:** answer Q1 + Q2 with the user, then draft a proper plan (data model deltas, auto-build rewrite, migration). Track as a phase, not a one-off PR.

### 🟢 Teacher has no way to generate an LP

**Symptom:** Today only the org's admin (via dashboard) or the integrator's API key can trigger LP generation — through `POST /api/v2/breakdowns/{id}/publish` (batch) or `POST /api/v1/quick-lp` (one-off). The teacher app reads pre-generated LPs off slots; it never asks for one.

**Why it matters:** real teachers will hit cases the breakdown didn't anticipate — substitution day, an unplanned recap, a topic the auto-build missed. They should be able to spin up an LP on the spot.

**Proposed:**
- Add a "Generate LP" affordance in the teacher app — either on a slot ("regenerate this LP") or freeform ("LP for this topic, this lp_type").
- Backend already supports it (`/api/v1/quick-lp` accepts `X-API-Key`, which the teacher app has via session). The work is UI + wiring.
- Decide auth surface: today *any* `X-API-Key` for the org can call quick-lp. If we want per-teacher quotas or audit-by-teacher, that's a separate harden.

**Open:** does generation tie to a specific slot (so the result lands on a CST schedule), or is it freeform and the teacher pastes/uses it ad-hoc? Probably both modes — slot-bound regenerate vs. ad-hoc quick-LP.

---

## Conventions for this file

- Add entries as you find them; don't wait for a session retrospect.
- Set status: 🟢 next up · 🟡 known, deferred · ⚪ open question.
- When something ships, move it to a `## Closed` section at the bottom with PR # and date.

---

## Closed

- **Breakdowns page → org-scope only with derived labels.** Dashboard `/breakdowns` now lists only the org's own master plans, labelled `{curriculum} · {grade} · {subject}`. Global breakdowns moved to a new "Templates" tab under `/dashboard/curriculum` where they can be forked. 2026-05-19.
- **LP UI shows covered SLOs.** The lesson-plan viewer (`components/molecules/lp-viewer.tsx`) now renders a "Covered SLOs" chip group above the LP HTML, fetching sub-SLO statements via `/api/v2/sub-slos/{id}`. Handles `pending`/`failed` tagging states. 2026-05-19.
- **Dashboard ↔ teacher-app nav.** Dashboard header has a "Teacher app demo →" link; teacher-app top bar has "← Dashboard". 2026-05-19.
