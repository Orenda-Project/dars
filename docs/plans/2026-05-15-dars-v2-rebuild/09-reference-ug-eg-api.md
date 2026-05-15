# Reference: UG_EG (Exam Generator) API

**Source:** [../../../../UG_EG](../../../../UG_EG)  
**Verified against SHAs:**
- `main`: `f46e671c598912a320130660738c4466d3967688`
- `origin/Staging`: `5454164cb175b892c3de1707325b05db80dd4129`

Both as of 2026-05-15.

**Critical note:** `page_content` request field exists on **`origin/Staging`**, not yet on `main`. By the time dars Phase 3 ships, this should be merged to main. **Re-verify** at Phase 3 start by checking:

```bash
cd /home/hataf/taleemabad/UG_EG
grep -n "page_content" main.py | head -5
git log -1 --format='%H %s' origin/main
```

If `page_content` is still only on `Staging`, dars Phase 3 either waits for the merge or coordinates with Shujaan.

---

## Endpoints

| Endpoint | Method | Type | Use in dars |
|---|---|---|---|
| `/api/generate-exam` | POST | Sync (45–60s) | Don't use |
| `/api/v2/generate-exam` | POST | Async + webhook | **Use this** (D-39) |
| `/api/v2/webhook-status/{job_id}` | GET | Manual status poll | Use for `/refresh` (D-40) |

Base URL: `https://exam-generator-staging.taleemabad.com` (staging) — confirm at deploy time.

---

## Request body (v2)

Fields dars **sends**:

| Field | Type | Notes |
|---|---|---|
| `callback_url` | str | `https://dars-staging.taleemabad.com/api/v1/webhooks/exam/{job_id}` |
| `generation_type` | str | `"exam"` or `"class_assessment"`. Both currently identical downstream; semantic only. |
| `curriculum` | str | `"ICT"` or `"Punjab"`. Mapped via **D-61**: DARS→ICT, NCP→ICT, SNC→Punjab. |
| `grade` | int | 1–5. |
| `subject` | str | `"Eng" \| "Urdu" \| "Maths" \| "Islamiat" \| "GenSci" \| "GenK" \| "SST"`. Note: UG_EG supports more subjects than LP Assistant. |
| `page_content` | str | **(Staging branch as of 2026-05-15)** — raw OCR text. Concatenate the topic_texts for the assessment's covered topics, separator `\n\n`. When provided, service skips DB lookup. |
| `page_ranges` | str | Required only if `page_content` is not provided. Format: `"1, 3, 5"` or `"1-3, 5-7"`. |
| `question_types` | list[str] | One or both of `["seen", "unseen"]`. For dars v1: usually `["unseen"]`. |
| `unseen_categories` | list[str] | Required if `"unseen"` in question_types. One or both of `["objective", "subjective"]`. |
| `unseen_objective_types` | list[str] | If `"objective"` in unseen_categories. Subject-specific (see below). |
| `unseen_subjective_types` | list[str] | If `"subjective"` in unseen_categories. Subject-specific. |
| `unseen_objective_counts` | dict[str, int] | Exact counts per type. e.g. `{"MCQs": 5, "True/False": 3}`. |
| `unseen_subjective_counts` | dict[str, int] | Same. |
| `long_question_sub_types` | list[str] | Maths-only. Allowed: `["Word Problems", "Graphs & Geometric Problems"]`. |
| `include_answer_key` | bool | dars sends `True` — we want answer text. |

Fields dars **does NOT send**:

| Field | Why not |
|---|---|
| `custom_system_prompt` | Not needed for v1. |
| `seen_categories` | Only used if `"seen"` in question_types; v1 uses unseen-only. |
| `image_generation_enabled` | Skip for v1. |
| `enable_review` | Adds 30–60s cost; defer. |

---

## Subject-specific question types

### Objective types

**Eng / Urdu:**
```
MCQs, MSQs, Fill in the Blanks, Missing Letters, True/False, Match Columns,
Circle the Correct, Rewrite Sentences, Brief Answers, Listening, Speaking, Reading
```

**Maths:**
```
MCQs, MSQs, Fill in the Blanks, True/False, Match Columns, Mental Math,
Missing Gaps, Sequences
```

### Subjective types

**Eng / Urdu:**
```
Word Meanings, Word Sentences, Comprehension, Rewriting, Story Completion,
Simple Writing, Formal Letter, Informal Letter, Application Writing, Story Writing,
Essay Writing, Paragraph Writing, Picture Description, Project Work, Brief Answers,
Mind Map, Label the Diagram, Flow Chart, Logical Reasoning
```

**Maths:**
```
Short Questions, Restricted Questions, Long Question
```

For Maths "Long Question," the `long_question_sub_types` field accepts:
```
Word Problems, Graphs & Geometric Problems
```

---

## dars's default exam configs (set by the breakdown engine)

| Slot type | Subject (G1 Eng v1 example) | Config |
|---|---|---|
| FA (formative) | English G1 | `question_types=["unseen"]`, `unseen_categories=["objective"]`, `unseen_objective_types=["MCQs", "True/False", "Fill in the Blanks"]`, counts: `{"MCQs": 5, "True/False": 3, "Fill in the Blanks": 2}` |
| SA (summative) | English G1 | `unseen_categories=["objective", "subjective"]`, objective ~12 questions mixed; subjective: `["Brief Answers", "Word Meanings"]` ~6 questions. Total ~18. |

These are starting defaults; Phase 2's breakdown engine can vary them per chapter.

---

## Response (v2 immediate)

```json
{ "status": "success", "job_id": "uuid" }
```

Status 202.

---

## Webhook payload

POST to our `callback_url`. Header: `X-Webhook-Secret`. Body:

```json
{
  "job_id": "uuid",
  "status": "completed" | "failed",
  "timestamp": "ISO8601-UTC",
  "data": {
    "status": "success",
    "exam_paper": "<html>...</html>",
    "exam_json": {
      "seen": { ... } or absent,
      "unseen": {
        "objective": {
          "MCQs": [ { "main_question": "...", "question": "...", "options": [...], "marks": 1, "answer": "...", "blooms": "Remember" }, ... ],
          "True/False": [ ... ],
          ...
        },
        "subjective": {
          "Brief Answers": [ { "main_question": "...", "question": "...", "marks": 2, "lines": 3 }, ... ],
          ...
        }
      }
    },
    "page_content": "echoed",
    "tags": { ... },
    "metadata": {
      "timings": { ..., "total_time": float },
      "tokens": {
        "input_tokens": int,
        "output_tokens": int,
        "total_tokens": int,
        "cost_usd": float
      },
      "total_cost_usd": float
    }
  }
}
```

On failure: `{ "job_id": "...", "status": "failed", "error": "...", "timestamp": "..." }`.

dars persists:
- `data.exam_json` → `generated_exams.result`
- `data.exam_paper` → `generated_exams.exam_paper_html`
- `data.metadata.total_cost_usd` → `generated_exams.cost_usd`
- `data.metadata.tokens.input_tokens` / `output_tokens` → `tokens_input` / `tokens_output`
- Full body → `generated_exams.ug_eg_response_raw`

---

## Question structure (inside `exam_json.unseen.objective.MCQs[i]` etc.)

| Field | Type | Notes |
|---|---|---|
| `main_question` | str | Section heading (e.g. "Choose the correct option") |
| `question` | str | The actual question text |
| `marks` | int | |
| `lines` | int | 0 for objective; positive for subjective (answer line count) |
| `answer` | str | Present only if `include_answer_key=True` |
| `blooms` | str | Bloom's level: Remember / Understand / Apply / Analyze / Evaluate / Create |
| `image` | str | Optional image prompt |
| `options` | list[str] | MCQ/MSQ only |
| `column_a` / `column_b` | list[str] | Match Columns only |
| `words` | list[str] | Word Meanings only |
| `passage` + `questions` | str + list | Comprehension only |

The question_index used by dars's post-process tagging (F3.9) is `(category, type, position_within_type)`.

---

## Authentication

- Header: `api-key: <value>`. Value from env var `UG_EG_API_KEY`.
- Same convention as LP Assistant.

---

## Curriculum and grade coverage

| Curriculum | Grades 1–3 | Grades 4–5 |
|---|---|---|
| ICT | Eng, Maths, Urdu, Islamiat, GenK | Eng, Maths, Urdu, Islamiat, GenSci, SST |
| Punjab | Eng, Maths, Urdu | Eng, Maths, Urdu |

Sindh is **not** supported by UG_EG yet. If dars sends Sindh, expect failure. Validate on our side first.

---

## What's NOT supported by UG_EG today

- SLOs as input (we tag on our side post-process — F3.9).
- Dars Curriculum directly (we map DARS → ICT for v1).
- Per-question Bloom's level control (LLM picks; we don't control).
- Difficulty control beyond grade.

---

## Re-verifying this doc

```bash
cd /home/hataf/taleemabad/UG_EG && git log -1 --format='%H %s' origin/main
grep -n "page_content" main.py
grep -n "VALID_OBJECTIVE_TYPES\|VALID_SUBJECTIVE_TYPES" config.py
```

If anything differs from this doc, **update this doc first**, then check downstream code.
