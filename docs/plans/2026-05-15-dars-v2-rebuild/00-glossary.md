# Glossary

Read this first. Terms used inconsistently across the codebase historically; this document is the source of truth. If code disagrees with this file, code is wrong.

---

## Tenancy

**Org (Organization)** — Top-level tenant. A chain or network of schools, billed as one entity, owns one API key for SDK access, picks **one** curriculum at signup (Decision 25). Replaces the legacy `Client` model. Org has zero or more `OrgAdmin` users (email/password auth, per Decision 17).

**School** — A physical school under an Org. Has its own academic year, holiday list (can override Org defaults), teachers, classes. New entity in v2.

**Teacher** — A teacher belongs to a School. No login (the teacher app is auth-free sample integration; real authentication is the integrating org's responsibility per Q9). Identified to dars by `teacher_id` which the org's app sends with each call.

**Class (SchoolClass)** — A class within a School, scoped to an Academic Year. E.g. "Grade 1, Section A, 2026–2027." Has a Grade and a Section.

**CST (ClassSubjectTeacher)** — The atomic teaching unit: one teacher teaches one subject to one class. The breakdown, slots, progress, and timetable all hang off CST. A teacher with multiple classes/subjects has multiple CSTs; each has independent progress (Decision 8).

**OrgAdmin** — A human who logs into the dashboard to manage their Org. Email/password. Can manage all Schools/Teachers/CSTs/Breakdowns within their Org.

---

## Curriculum hierarchy

**Curriculum** — A pedagogical standard with SLOs, books, etc. Examples: *Dars Curriculum* (our authored default for v1), *NCP* (Pakistan National), *SNC* (Punjab provincial), future *Palestine*, *Tanzania*. Global; one Org picks one Curriculum at signup. Curricula are not editable by Orgs (Decision 24).

**Grade** — A school grade level. `1..12`. Global lookup table.

**Subject** — A subject taxonomy aligned with what LP Assistant and UG_EG support: `Eng`, `Urdu`, `Maths`, `Science`, `GK`, `Islamiat`, `GenSci`, `SST`. Global lookup. (LP Assistant supports the first 5; UG_EG supports all 8.)

**SLO (Student Learning Outcome)** — A curriculum-level outcome. Scoped to `(curriculum, grade, subject)`. E.g. "Student can read CVC words" (English G1, Dars Curriculum). Has a code (e.g. `A1-02`) and a statement. Sourced from curriculum standards; for Dars Curriculum, hand-authored in the seed.

**SubSLO (Sub-SLO)** — A granular, atomic teaching unit derived from an SLO via Schema's LLM breakdown. Many-to-one with SLO. E.g. SLO "Student can add two-digit numbers" might have sub-SLOs "identify place value," "add without carrying," "add with carrying." Topics link to sub-SLOs, not SLOs (Decision Q5). Generated eagerly during seed + manual trigger for ad-hoc additions (Decision 3).

---

## Book hierarchy

**Book** — A textbook scoped to `(curriculum, grade, subject)`. Has OCR'd `book_text` (JSONB array of `{pdf_page_no, text}`). Books are global within a curriculum — multiple orgs using the same curriculum share the same Book record.

**BookChapter** — A chapter within a Book. Has `chapter_number`, `start_page`, `end_page`, and `chapter_text` (OCR slice for this chapter). Linked to SLOs many-to-many (a chapter teaches these SLOs).

**Topic** — A book-specific section within a BookChapter, defined by line-number boundaries within `chapter_text`. Has `topic_number`, `title`, `start_line`, `end_line`, and `topic_text` (OCR slice for this topic). Linked to sub-SLOs many-to-many — these are the sub-SLOs this topic teaches. Topic boundaries are LLM-drafted, admin-published (Decision 4).

---

## Breakdown system

**Breakdown** — The plan for how to teach a `(curriculum, grade, subject)` over an academic year. The atomic unit; immutable once published.

**Scope of a Breakdown** — Three levels:
- **Global** — Dars-authored canonical. One per `(curriculum, grade, subject)`.
- **Org** — A fork of Global owned by one Org. Applies to all Schools in that Org (Decision 23). One per Org per `(curriculum, grade, subject)`.
- **Class** — A fork of Org (or Global if Org didn't fork) owned by one CST. One per CST.

**Parent** — Every Breakdown except Global has a `parent_breakdown_id`. Forking is a full copy of the parent at fork-time. No automatic upstream pulls (Decision 18).

**BreakdownSlot** — One row of a Breakdown. Represents either a lesson slot or an assessment slot in sequence. Has `position` (sequence position 1..N), `slot_type` (`lesson` | `assessment_formative` | `assessment_summative` | `revision`), `lp_type` (only valid LP Assistant types per Decision Q5 — see below), `topic_id` (for lesson/revision), `topic_id_set` (for assessments covering multiple topics), `anchor_date` (optional, admin-only per Decision 7).

**ClassLessonSlot / AssessmentSlot** — The realized BreakdownSlot for one CST. References the BreakdownSlot it was created from. Holds the per-class state: status, `generated_lp_id` / `generated_exam_id`. Created when a Class's Breakdown is finalized.

**Sequence position** — Integer 1..N. Primary key into a Breakdown's slot order. Calendar dates are computed by projecting sequence position onto the CST's teaching days (Decision 4 of round 1: sequence-only model with anchors).

**Anchor (anchor_date)** — Optional date pinned to a BreakdownSlot. Only admins can set anchors (Decision 7). When projecting sequence to calendar, anchored slots fix their date; the sequence fills around them.

**Current sequence position** — A CST's progress pointer. Defined as "highest `position` of any slot with a `taught` event, plus 1." Out-of-order completion is allowed; gaps stay visible (Decision 11).

**Teaching day** — A calendar day on which a CST teaches. Computed from `academic_year.start_date..end_date`, intersected with the CST's timetable's `day_of_week` set, minus holidays applicable to that CST (Org → School → Teacher inheritance per Decision 26).

---

## Holidays and timetable

**Holiday** — A no-teach day. Three-level inheritance (Decision 26):
- **Org** level — applies to all schools (default national holidays).
- **School** level — adds or removes Org holidays.
- **Teacher (CST)** level — adds or removes School holidays (e.g. sick days).

The effective holiday set for a CST is computed at projection time.

**Timetable** — Which days of the week a CST meets. Per-CST only (Decision 27). Default Mon–Fri (0..4, with Monday=0). Stored as `timetables.day_of_week`. No school-level default in v1.

---

## LP / Exam generation

**lp_type** — The pedagogical type of a lesson plan. The valid values per subject (sourced from LP Assistant `VALID_LP_TYPES`):
- `Eng`, `Urdu`: `reading`, `comprehension_word_meanings`, `comprehension_qa`, `grammar`, `creative_writing`, `revision`
- `Maths`: `concrete`, `pictorial_and_abstract`, `word_problems`, `revision`
- `Science`, `GK`: `revision` only

Any `lp_type` the breakdown produces MUST be in this enum. Sending an invalid value causes LP Assistant to silently fall back to "regular" which produces poor output.

**GeneratedLP** — A cached LP. **Keyed by (curriculum, topic, lp_type)** for non-revision LPs, or `(curriculum, [topic_ids], lp_type=revision)` for revisions. Reused across CSTs that need the same combination (Decision 46). Stored with cost metadata (Decision 10). Status: `PENDING | IN_FLIGHT | READY | ERROR`. Linked to ClassLessonSlots that consume it.

**GeneratedExam** — A cached exam. Keyed by `(curriculum, [topic_ids], generation_type, question_types_config_hash)` (Decision 47). Reused across CSTs. Same status lifecycle as GeneratedLP.

**page_content** — Raw OCR text we send to LP Assistant and UG_EG as the source material. Provided in the request body; both services accept it (LP Assistant on `main`; UG_EG on `Staging` branch as of plan-write date). When `page_content` is provided, the services skip their internal DB lookup (we control the world).

**SLO tagging** — A post-process step. After LP Assistant returns an LP, we send it back through Schema's `lp_tagging` module to extract which sub-SLOs the LP actually covered (Decision 22). The tag set is stored as `generated_lps.covered_sub_slo_ids`. For exams, each question is similarly tagged to a sub-SLO post-generation.

---

## Mark-taught and progress

**SlotProgress** — Event log of teaching actions. Append-only. One row per `(CST, slot, action)`. Actions: `taught`, `skipped`, `taught_before_dars` (for mid-year onboarding — not used in v1 declarative model). The plan is immutable; progress is the event log (Decision F4 from architecture round).

**Mark-taught flow** — Teacher marks a slot taught → `SlotProgress` row inserted → all sub-SLOs linked to the slot's topic flip to taught for that CST (Decision 5).

**Mid-year join** — Teacher (or org admin) declares "I'm at chapter X, day Y" on onboarding (Decision 12). Sets `cst_state.current_sequence_position` directly. Slots before that position remain unmarked (no `SlotProgress` rows). SLO coverage report shows them as "unknown."

**Mastery** — Class-level only in v1 (Decision 31). After an FA/SA, teacher enters per-question "how many of N students got this right" via the teacher app (Decision 32). Roll up to per-sub-SLO mastery using each question's sub-SLO tag.

---

## Async generation

**Webhook + manual poll** — Both LP Assistant v3 and UG_EG v2 are async with webhook callbacks (Decisions 38–39). When we POST a generation request, we store the `job_id`. The service POSTs to our webhook when done. We also expose a manual `/refresh` endpoint to pull status on demand (Decision 40 — for local dev, debugging, prod fallback).

**callback_url** — The URL we send in each generation request. Environment-specific: `https://dars-staging.taleemabad.com/api/v1/webhooks/{lp|exam}/{job_id}`. Webhook handler is idempotent by job_id (Decision 43).

**Webhook secret** — Shared-secret header (`X-Webhook-Secret`). Both LP Assistant and UG_EG include it in callbacks; dars verifies (Decision 41).

**Batch generation** — When a Breakdown is finalized, dars fires async generations for all its slots whose `(topic, lp_type)` doesn't already have a cached LP (Decision 46 + 49). Dashboard shows live progress.

---

## Misc

**Generation cost** — Both services return `cost_usd` in metadata. Stored per generation row from day one (Decision 10).

**Bead** — Project work-tracking unit. One bead per phase (Decision 54). Opens when phase execution starts; closes when phase is on staging.

**Phase** — A discrete chunk of the rebuild that ends with a staging deploy. Phases 1–5 in this plan (Decisions 16, 51).
