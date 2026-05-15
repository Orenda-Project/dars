# Phase 3: Generation Pipeline

**Goal:** Real LP and Exam generation against LP Assistant v3 and UG_EG v2, with caching, webhook handling, manual poll, and post-process SLO tagging.

**Bead:** `feat-v2-phase-3-generation`.

**Pre-reqs:** Phase 2 complete on staging.

**Deliverables:**
- LP Assistant v3 client with `page_content` and `lp_type`
- UG_EG v2 client with `page_content` and full question config
- Caching by `(curriculum, topic, lp_type)` for LPs and `(curriculum, [topics], gen_type, config_hash)` for exams
- Class-scoped overrides when slots are custom (per D-57)
- Webhook handlers for both LP and Exam, idempotent + shared-secret auth
- Manual poll endpoint `/refresh`
- Post-process LP tagging using Schema's `lp_tagging.py`
- Post-process exam question SLO tagging
- Cost tracking on every generation
- Batch generation flow: publishing a class breakdown enqueues all missing LPs/Exams

**NOT in this phase:** FE batch-progress UI (Phase 5), teacher app integration (Phase 4).

---

## Feature order

1. **F3.1** — Port Schema's `lp_tagging.py` into dars
2. **F3.2** — LP Assistant v3 client
3. **F3.3** — UG_EG v2 client
4. **F3.4** — Generated LP cache lookup/insert + class-scope branching
5. **F3.5** — Generated Exam cache lookup/insert + class-scope branching
6. **F3.6** — Webhook handlers (lp + exam) with shared-secret + idempotency
7. **F3.7** — Manual refresh endpoints
8. **F3.8** — Post-generation LP tagging service
9. **F3.9** — Post-generation exam question tagging service
10. **F3.10** — Revision LP path (multi-topic `page_content`)
11. **F3.11** — Batch generation on breakdown publish
12. **F3.12** — Cost tracking + per-org usage report endpoint
13. **F3.13** — Failure handling: status=ERROR surface (D-50)

---

## F3.1 — Port `lp_tagging.py`

**Motivation:** Used in F3.8 to post-process every generated LP.

**Spec:**
- Source: `Schema/services/lp_tagging.py`, `prompts/lp_tagging_prompt.txt`, `schema-tags.json`
- Destination: `dars/breakdown/lp_tagging_service.py`, prompt copied to `dars/breakdown/prompts/`, tag taxonomy copied to `dars/breakdown/schema-tags.json`
- Convert sync to async
- Function: `async def tag_lp(lp_html: str, sub_slo_candidates: list[SubSLO]) -> TaggingResult`
- Input: LP HTML + list of sub-SLOs the LP is *expected* to cover (from the slot's topic)
- Output: TaggingResult = `{ covered_sub_slo_ids: [...], pedagogical_tags: {...}, raw_response: dict }`
- Use the same LLM (Claude or GPT-4o) and credentials as elsewhere

**Test plan:** mock LLM; verify response parsing produces sub_slo_id list.

**Acceptance:** module compiles, returns structured tagging.

---

## F3.2 — LP Assistant v3 client

**Motivation:** Replace the sync v1 call dars uses today.

**Spec:**
- File: `dars/generated_lps/lp_assistant_client.py`
- Async HTTP client using `httpx.AsyncClient`
- Endpoint: `POST {LP_ASSISTANT_URL}/api/v3/generate-lp`
- Headers: `api-key: {LP_ASSISTANT_API_KEY}`
- Request body fields we send:
  - `curriculum: 'ICT' | 'Punjab' | 'Sindh'` — mapped from our `curriculums.code` per **D-61**:
    - `DARS` → `ICT`
    - `NCP` → `ICT`
    - `SNC` → `Punjab`
    - Unknown code → fail fast with explicit error (no silent default)
  - `grade: int` (1-5; map from our `grades.code`)
  - `subject: str` (`'Eng' | 'Urdu' | 'Maths' | 'Science' | 'GK'`; map from our subject codes)
  - `page_content: str` (the topic's `topic_text`)
  - `lp_type: str` (must be in LP Assistant's `VALID_LP_TYPES[subject]`)
  - `class_strength: int = 30`
  - `generate_bilingual: bool = False`
  - `callback_url: str` (= `{DARS_BASE_URL}/api/v1/webhooks/lp/{job_id}`)
  - Do NOT send `topic` (Decision: skip)
  - Do NOT send `custom_prompt` (D)
  - Do NOT send `system_prompt`
  - Do NOT send `page_number` or `exercise_page_number`
- Response: 202 with `{ job_id: 'uuid' }`
- Function signature: `async def request_lp_generation(payload: LPRequest) -> str` → returns job_id
- Logs entry/exit/errors per Critical Rule #11

**Mapping concerns:**
- Curriculum mapping per **D-61** lives in `dars/breakdown/curriculum_mapping.py` and is shared by F3.3 (UG_EG client) too:
  ```
  CURRICULUM_TO_LP_ASSISTANT = {'DARS': 'ICT', 'NCP': 'ICT', 'SNC': 'Punjab'}
  CURRICULUM_TO_UG_EG       = {'DARS': 'ICT', 'NCP': 'ICT', 'SNC': 'Punjab'}
  ```
  Both clients import from the same source so a new curriculum + Shujaan-side support is one edit.
- Subject codes must match LP Assistant's. We seeded with codes that match (`Eng`, `Urdu`, `Maths`, etc.).

**Test plan:**
- Mock the HTTP call; verify request body has correct fields and ONLY those fields
- Verify mapping: curriculum_id → 'ICT', subject_id → 'Eng'

**Acceptance:** client sends spec-compliant requests; receives + returns job_id.

---

## F3.3 — UG_EG v2 client

**Motivation:** Same but for exams.

**Spec:**
- File: `dars/generated_exams/ug_eg_client.py`
- Endpoint: `POST {UG_EG_URL}/api/v2/generate-exam`
- Headers: `api-key: {UG_EG_API_KEY}`
- Request body fields:
  - `callback_url: str`
  - `generation_type: str = 'exam'`
  - `curriculum: 'ICT' | 'Punjab'` — mapped via `CURRICULUM_TO_UG_EG` per **D-61** (`DARS`/`NCP` → `ICT`, `SNC` → `Punjab`)
  - `grade: int`
  - `subject: str`
  - `page_content: str` (concatenated topic_texts for the exam's topics, joined with `\n\n`)
  - `question_types: list[str]` (`['unseen']` or `['seen']` or both)
  - `unseen_categories: list[str]` (`['objective', 'subjective']` typical)
  - `unseen_objective_types: list[str]` (subject-specific: see glossary)
  - `unseen_subjective_types: list[str]`
  - `unseen_objective_counts: dict[str, int]` (e.g. `{'MCQs': 5, 'Fill in the Blanks': 3}`)
  - `unseen_subjective_counts: dict[str, int]`
  - `include_answer_key: bool = True` (for our use case, we want the answer)
  - `enable_review: bool = False` (skip pedagogical review in v1)
- Response: 202 with `{ job_id }`
- Function: `async def request_exam_generation(payload: ExamRequest) -> str` → returns job_id

**Question config for the breakdown's default FAs and SAs:**
- **FA (formative, English G1, ~10 questions):** unseen objective only, mostly MCQs + True/False + Fill in Blanks; 10 total
- **SA (summative, English G1, ~20 questions):** unseen objective + subjective; ~12 obj + 8 subj; mix of MCQs, fill, T/F, and short comprehension/answers

These defaults are encoded in the breakdown engine when creating assessment slots (Phase 2). UG_EG client just sends what the slot says.

**Test plan:**
- Mock HTTP; verify body shape matches UG_EG's expected schema
- Cover all 4 subjects (Eng, Urdu, Maths, Science) with their valid question types

**Acceptance:** client sends spec-compliant requests.

---

## F3.4 — Generated LP cache lookup/insert + class-scope branching

**Motivation:** Per D-46 + D-56 + D-57, we cache LPs at the global level keyed on `(curriculum, topic, lp_type)`; class-scope LPs (when a CST's slot has a custom topic combo) live separately.

**Spec:**
- Service: `dars/generated_lps/service.py`
- Function: `async def get_or_generate_lp(cst_id, lesson_slot_id, db) -> GeneratedLP`
  - Look up the slot's `topic_id` + `lp_type`
  - For lesson slots (non-revision):
    - cache_key = `f"{curriculum_id}:{topic_id}:{lp_type}"`
    - Lookup: `SELECT * FROM generated_lps WHERE cache_key=? AND scope='global'`
    - If found and status='READY' → return existing; update slot.generated_lp_id
    - If found and status='PENDING'/'IN_FLIGHT' → return existing (caller waits via webhook or polls)
    - If found and status='ERROR' → re-request (treat as miss)
    - If not found → create new row with status='PENDING', request from LP Assistant, set status='IN_FLIGHT' + job_id
  - For revision slots: use the revision path (F3.10) — different keying
- Function: `async def get_or_generate_class_specific_lp(cst_id, lesson_slot_id, db) -> GeneratedLP`
  - Called when the slot's topic was custom-added by the teacher (not in the global breakdown's slot set)
  - cache_key = `f"{curriculum_id}:{cst_id}:{topic_id}:{lp_type}"` (includes cst_id)
  - Scope = 'class'; scope_ref_id = cst_id

**Test plan:**
- Cache hit: two CSTs with the same slot config share one GeneratedLP row
- Cache miss: triggers HTTP call to LP Assistant; row created
- Class-specific: a teacher with a custom slot gets its own row even if the topic+lp_type exists globally

**Acceptance:** caching works; HTTP calls are minimized.

---

## F3.5 — Generated Exam cache lookup/insert + class-scope branching

**Motivation:** Same as F3.4 but for exams.

**Spec:**
- Same shape, different keying:
  - `topic_ids_hash` = SHA-256(sorted(topic_ids)), where topic_ids are the assessment slot's covered topics
  - `question_config_hash` = SHA-256(canonical JSON of the question config dict)
  - cache_key = `f"{curriculum_id}:{topic_ids_hash}:{generation_type}:{question_config_hash}"`
- Class-scoped variant adds cst_id to the key

**Test plan:** same as F3.4 with exam payloads.

**Acceptance:** exam caching works.

---

## F3.6 — Webhook handlers (lp + exam)

**Motivation:** LP Assistant and UG_EG POST results to our `callback_url` (D-40).

**Spec:**
- Endpoint: `POST /api/v1/webhooks/lp/{job_id}`
  - Header check: `X-Webhook-Secret` matches env var `LP_ASSISTANT_WEBHOOK_SECRET` (D-41)
  - Body: LP Assistant's webhook payload (shape from the survey)
  - Insert audit row in `webhook_events` (D-43 audit)
  - Look up `generated_lps` by `job_id`
  - If status already terminal (READY/ERROR) → return 200 no-op (idempotent, D-43)
  - Else: extract `lesson_plan` (HTML), `lesson_plan_bilingual`, `cost_usd`, `tokens_*`, `model`
  - Update `generated_lps`: status='READY', content=html, cost_usd=cost, etc.
  - Trigger `lp_tagging` (F3.8) as a BackgroundTask
  - Return 200
- Endpoint: `POST /api/v1/webhooks/exam/{job_id}`
  - Same shape; updates `generated_exams`; stores `result` (JSON) and `exam_paper_html`
  - Triggers question tagging (F3.9) as BackgroundTask
- Failure cases: if the upstream job failed, update status='ERROR', error_message=...

**Security note:** use `hmac.compare_digest` for secret comparison (Critical Rule #5).

**Test plan:**
- Send a webhook with valid secret + valid payload → row updated; tagging enqueued
- Send with invalid secret → 403
- Send twice with same job_id → second is no-op
- Send with unknown job_id → 404

**Acceptance:** webhooks tested end-to-end against a mock LP Assistant.

---

## F3.7 — Manual refresh endpoints

**Motivation:** D-40 — for local dev (no public webhook URL) and debugging.

**Spec:**
- `POST /api/v1/generated-lps/{id}/refresh` → calls LP Assistant's `/api/v2/webhook-status/{job_id}` (the manual status endpoint they provide), pulls latest status, processes same as webhook
- `POST /api/v1/generated-exams/{id}/refresh` → same for UG_EG
- Use idempotent handler from F3.6 to avoid double-processing if webhook fires concurrently

**Test plan:**
- Generation in PENDING state; manual refresh → if LP Assistant says ready, our row updates
- After our row is READY, refresh is no-op

**Acceptance:** manual poll works.

---

## F3.8 — Post-generation LP tagging

**Motivation:** Every LP gets tagged so we know real SLO coverage (D-22).

**Spec:**
- Service: `dars/generated_lps/tagging_service.py`
- Background function triggered after webhook receives a successful LP
- Logic:
  1. Load the `generated_lps` row
  2. Determine candidate sub-SLOs: the sub-SLOs linked to the LP's `topic_id` (for non-revision LPs) or the union for revision LPs
  3. Call `lp_tagging_service.tag_lp(lp_html, candidates)` → returns the subset actually covered
  4. Update `generated_lps`: `covered_sub_slo_ids = [...]`, `tagging_status = 'done'`
  5. On failure: `tagging_status = 'failed'`

**Test plan:**
- Mock LP HTML + mock LLM response → verify `covered_sub_slo_ids` populated correctly
- Failure path → tagging_status='failed' but the LP itself is still usable

**Acceptance:** every LP that completes generation also gets tagged.

---

## F3.9 — Post-generation exam question tagging

**Motivation:** Per D-32, mastery rollup needs to know which sub-SLO each question tests.

**Spec:**
- Service: `dars/generated_exams/tagging_service.py`
- Background function triggered after webhook receives a successful exam
- Logic:
  1. Parse the `result` JSON: each question lives under `unseen.{objective|subjective}.{question_type}[]`
  2. Determine candidate sub-SLOs: the sub-SLOs linked to the assessment's covered topics
  3. For each question: pass question text + candidate sub-SLOs to LLM, ask which sub-SLO(s) the question tests
  4. Store as `question_sub_slo_tags: { '<question_index>': '<sub_slo_id>' }` in the `generated_exams` row
  5. Update `tagging_status='done'`

**Performance note:** for an exam with 20 questions, this is 20 LLM calls. Bound by per-org cost via cache: if the exam was cached, tagging is also cached (don't re-tag the same exam_id).

**Test plan:**
- Mock exam JSON + mock LLM → verify mapping
- Verify caching: re-tag is a no-op

**Acceptance:** every exam gets per-question sub-SLO tags.

---

## F3.10 — Revision LP path

**Motivation:** D-21 — revision LP gets `page_content` = concatenated topic_text of all prior topics in this chapter.

**Spec:**
- For revision-type slots, the cache key is `f"{curriculum_id}:revision:{topic_ids_hash}"` (where topic_ids = all topics in the chapter up to this slot)
- Build `page_content` = `"\n\n".join([topic.topic_text for topic in chapter.topics_before(this_slot)])`
- Send to LP Assistant with `lp_type='revision'`
- Everything else (webhook handling, tagging) is identical
- If `page_content` is huge (>20k tokens), truncate to the last N topics (configurable, default last 5 topics)

**Test plan:**
- Chapter with 4 topics; revision slot after the 4th → page_content includes all 4 topics
- Verify cache: two CSTs with same chapter share one revision LP

**Acceptance:** revision LPs generated with full context.

---

## F3.11 — Batch generation on breakdown publish

**Motivation:** D-46 — when a breakdown is published, fire async generation for every slot whose LP isn't yet cached.

**Spec:**
- Hook into the breakdown publish flow (F2.4 publish endpoint)
- After successful publish:
  - For global breakdown: iterate every lesson slot, call `get_or_generate_lp` (which will hit cache or fire a new request); same for assessment slots
  - For org breakdown: only generate for slots that differ from the parent global breakdown's slot set (most should hit cache)
  - For class breakdown: same — only differing slots
- BackgroundTask: fire-and-forget
- Each generated_lps/generated_exams insert immediately gets status='PENDING'; webhook moves to READY
- Dashboard can query `GET /api/v1/breakdowns/{id}/generation-status` → returns `{ total: 180, pending: 0, in_flight: 12, ready: 165, error: 3 }` (D-49)

**Test plan:**
- Publish a class breakdown that's a verbatim fork of org → assert zero new generation requests (all cached)
- Publish a class breakdown with one custom slot → assert one new generation request
- Generation status endpoint reflects counts correctly

**Acceptance:** publishing efficiently uses cache and minimizes LLM calls.

---

## F3.12 — Cost tracking + per-org usage report

**Motivation:** D-10 — we track cost from day one.

**Spec:**
- `generated_lps.cost_usd` and `generated_exams.cost_usd` populated from LP Assistant / UG_EG response metadata (already in F3.6)
- Endpoint: `GET /api/v1/orgs/me/usage?start=YYYY-MM-DD&end=YYYY-MM-DD`
- Returns: `{ lp_count, exam_count, total_cost_usd, by_subject: {...}, by_curriculum: {...} }`
- Cost attribution: a cached LP that's "reused" by an org doesn't double-charge — we count the LP's cost once across all CSTs that link it. Org-level cost attribution is by *creation org* (the first org that triggered the cache miss bears the cost in v1). This is fine because in v1 the global breakdown's batch pre-generation creates everything before any org/class consumes it; cost attributes to "Dars system" (we eat it).
- v2 will refine attribution (proportional, or "each org pays when they consume").

**Test plan:** create some generations; verify usage endpoint sums correctly.

**Acceptance:** usage report works.

---

## F3.13 — Failure handling

**Motivation:** D-50 — when LP generation fails, teacher sees "LP unavailable" but can still mark taught.

**Spec:**
- When LP Assistant webhook returns failure: status='ERROR', error_message populated
- API endpoint `GET /api/v1/class-lesson-slots/{id}` returns the slot with `lp_status='ERROR'` and `lp_error_message=...`
- Teacher app (Phase 4) shows "LP unavailable — contact admin" but Mark Taught button still works
- Admin dashboard (Phase 5) shows failed LPs list with a retry button

**Test plan:**
- Mock failure → slot shows error state
- Mark-taught still works on failed-LP slot

**Acceptance:** errors don't block teaching.

---

## Phase 3 wrap-up checklist

- [ ] LP Assistant v3 client + UG_EG v2 client work end-to-end against staging services
- [ ] Webhooks receive callbacks with shared-secret auth
- [ ] Manual refresh endpoints work
- [ ] LP cache + class-scope cache populated correctly
- [ ] Tagging runs on every successful LP/Exam
- [ ] Batch generation on publish fires async requests
- [ ] Cost tracked on every row
- [ ] Failure path doesn't break teacher flow
- [ ] All endpoints documented
- [ ] Staging deployed; manual end-to-end test green (publish breakdown → wait → all LPs READY → SLO coverage updates on mark-taught)
