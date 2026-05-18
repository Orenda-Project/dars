# Dars product backlog

Running list of UX, UI, and behavior issues found while QA'ing staging. Each entry: what's wrong, why it matters, proposed fix. Triage status: 🟢 next up · 🟡 known, deferred · ⚪ open question.

Not to be confused with `.claude/improvements.md`, which captures harness/agent improvements, not product.

---

## Dashboard

### 🟢 Breakdowns page should be org-scope only

**Symptom:** `/dashboard/breakdowns` lists every breakdown the org owns — global, org, and class. For a school with 30 classes × 5 subjects that's 150+ rows, mostly class-scope auto-realized copies that admins never edit.

**Why it matters:** the dashboard is for the *client* (school admin / developer). They author at the org level. Class-scope is teachers' surface, reachable from the class detail page.

**Proposed:**
- `/dashboard/breakdowns` → org-scope only.
- Global breakdowns ("templates to fork") move to the Curriculum tab where books and SLOs already live.
- Class breakdowns reachable from `/dashboard/schools/{school}/classes/{class}` (read-only summary + "this class follows org breakdown; overrides shown here").

**Open:** confirm class-detail page treats its breakdown as read-only vs. allowing slot/anchor tweaks. Real admin edits at class scope are rare; teachers do it implicitly via mark-taught/skip.

### 🟢 Breakdowns need human-readable labels

**Symptom:** the list shows raw `scope` tags ("global", "org", "class") with no name. No `name` column exists on the `breakdowns` table.

**Proposed:** derive a label from the joins:
```
{curriculum_code} · {grade.display_name} · {subject.code} ({scope})
e.g. "DARS · Grade 1 · Eng (org)"
```
Class-scope appends `{school} {class.name}-{section}`.

No schema change needed; this is a webapp render fix (and the server may want to surface joined fields on the list endpoint to save N+1 lookups).

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

### 🟢 LP UI doesn't show covered SLOs / sub-SLOs

**Symptom:** When a teacher (or admin) views a generated LP, the rendered output shows the lesson content but doesn't surface which sub-SLOs the LP actually covers. The backend already tags this (`generated_lps.covered_sub_slo_ids`, surfaced on slot detail as `lp_covered_sub_slo_ids`), but the UI ignores it.

**Why it matters:** teachers should know what learning outcomes the lesson is hitting — otherwise the SLO framework is invisible to the people actually teaching. Also useful for the dashboard admin to verify coverage.

**Proposed:** at the top of every rendered LP (teacher app + dashboard), show a "Covered SLOs" chip group. Click a chip → see the sub-SLO statement. Read directly from the slot detail response; no new endpoint needed.

**Note:** tagging is async — `lp_tagging_status` is `pending` → `done` (or `failed`). UI should handle the in-flight state ("SLO tags pending…") gracefully.

### 🟢 No navigation between dashboard and teacher app

**Symptom:** A user on `/dashboard/*` has no way to jump to `/teacher-app/*`, and vice versa. They're two distinct surfaces (admin vs. teacher demo) but share the same session/org, and during demos / QA we constantly need to switch between them.

**Why it matters:** the teacher app exists to show clients "this is what a teacher's experience could look like" — but if they can't even find it from the dashboard, the demo value disappears. Same in reverse: a teacher demoing the app may want to glance back at the dashboard.

**Proposed:** add a top-bar entry (or footer link) on each shell that links to the other:
- Dashboard shell → "View teacher app demo →" (deep-links to `/teacher-app/today`)
- Teacher app shell → "← Back to dashboard"

Both should reuse the existing session — no re-auth required.

---

## Conventions for this file

- Add entries as you find them; don't wait for a session retrospect.
- Set status: 🟢 next up · 🟡 known, deferred · ⚪ open question.
- When something ships, move it to a `## Closed` section at the bottom with PR # and date.
