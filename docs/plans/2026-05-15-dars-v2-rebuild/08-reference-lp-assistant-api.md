# Reference: LP Assistant API

**Source:** `/home/hataf/taleemabad/UG_LessonPlan`  
**Verified against SHA:** `8ab979df488ecd1d0377b0f5051695fe48833fa2` (branch: `main` at 2026-05-15)  
**Re-verify before quoting line numbers** — repo may have rebased.

This is what dars's Phase 3 LP client (F3.2) must match.

---

## Endpoints

| Endpoint | Method | Type | Use in dars |
|---|---|---|---|
| `/api/generate-lp` | POST | Sync (60–120s) | Don't use |
| `/api/v2/generate-lp` | POST | Sync + extra fields | Don't use |
| `/api/v3/generate-lp` | POST | Async + webhook | **Use this** (D-38) |
| `/api/v2/webhook-status/{job_id}` | GET | Manual status poll | Use for `/refresh` endpoint (D-40) |

Base URL: `https://lp-assistant-staging.taleemabad.com` (staging) — confirm with user at deploy time.

---

## Request body (v3)

Fields dars **sends**:

| Field | Type | Notes |
|---|---|---|
| `curriculum` | str | One of `ICT \| Punjab \| Sindh`. Mapped from `curriculums.code` per **D-61**: DARS→ICT, NCP→ICT, SNC→Punjab. |
| `grade` | int | 1–5. Map from `grades.code`. |
| `subject` | str | One of `Eng \| Urdu \| Maths \| Science \| GK`. Map from `subjects.code`. |
| `page_content` | str | Raw OCR text. Fed directly to the LLM. When sent non-empty, service skips its internal DB lookup. **THIS IS HOW WE INJECT TOPIC CONTEXT.** |
| `lp_type` | str | Subject-specific enum (see below). Defaults to "regular" which produces low-quality output — **always send this**. |
| `class_strength` | int | Default 30. |
| `generate_bilingual` | bool | Default False. |
| `callback_url` | str | `https://dars-staging.taleemabad.com/api/v1/webhooks/lp/{job_id}` — we generate the job_id on our side first. |

Fields dars must **NOT send** (per design decisions in conversation):

| Field | Why not |
|---|---|
| `topic` | User said don't use. We feed semantic context through `page_content` instead. |
| `custom_prompt` | User said don't use. |
| `system_prompt` | Power-user override; out of scope for v1. |
| `page_number` | Ignored when `page_content` is provided; redundant. |
| `exercise_page_number` | Only relevant when fetching from service's DB. We provide content directly. |
| `enable_review` | Adds 30–60s cost; defer to v2. |
| `revision_lp` | Use `lp_type='revision'` instead — selects same prompt. |
| `is_objective` / `is_subjective` | Only relevant with `revision_lp` flag. |
| `image_generation_enabled` | Out of scope for v1. |
| `feedback` | For future "regenerate with feedback" flow; v1 doesn't regenerate (D-48). |
| `selected_model` | Don't pin model; let service choose. |
| `sub_region` (v2 only) | Punjab-specific framework injection; v1 doesn't use. |

---

## `lp_type` enum (CRITICAL — see D-61 + glossary)

Source of truth: LP Assistant's `config.py` `VALID_LP_TYPES`.

| Subject | Allowed values |
|---|---|
| `Eng` | `reading`, `comprehension_word_meanings`, `comprehension_qa`, `grammar`, `creative_writing`, `revision` |
| `Urdu` | same 6 as Eng |
| `Maths` | `concrete`, `pictorial_and_abstract`, `word_problems`, `revision` |
| `Science` | `revision` only |
| `GK` | `revision` only |

**The breakdown engine MUST emit only these values.** Anything else makes LP Assistant silently fall back to "regular" (bad output).

The current dars code (pre-rebuild) sends invalid values like `"Concept"`, `"Practice"`, `"Qiraat"`, `"Lughat"` — these are all bugs explaining current low quality.

---

## Response (v3 immediate)

```json
{ "job_id": "uuid-string" }
```

Status 202.

---

## Webhook payload (when generation completes)

POST to our `callback_url`. Headers include `X-Webhook-Secret` (shared secret per D-41). Body:

```json
{
  "job_id": "uuid",
  "status": "completed" | "failed",
  "timestamp": "ISO8601-UTC",
  "data": {
    "status": "success",
    "lesson_plan": "<html>...</html>",
    "lesson_plan_bilingual": "<html>...</html>" or "",
    "page_content": "echoed back",
    "tags": { "grade": int, "subject": str, "page_number": null, ... },
    "metadata": {
      "timings": { ..., "total_time": float },
      "tokens": {
        "lesson_plan_generation": {
          "input_tokens": int,
          "output_tokens": int,
          "total_tokens": int,
          "model": "google/gemini-3.1-pro-preview",
          "cost_usd": float,
          "elapsed_time": float
        },
        "costs": { "total_usd": float },
        ...
      }
    },
    "review": null
  }
}
```

dars must persist:
- `data.lesson_plan` → `generated_lps.content`
- `data.lesson_plan_bilingual` → `generated_lps.content_bilingual`
- `data.metadata.tokens.lesson_plan_generation.cost_usd` → `generated_lps.cost_usd`
- `data.metadata.tokens.lesson_plan_generation.input_tokens` / `output_tokens` → `generated_lps.tokens_input` / `tokens_output`
- `data.metadata.tokens.lesson_plan_generation.model` → `generated_lps.model`
- Full body → `generated_lps.lp_assistant_response_raw` (debugging)

On failure (`status: "failed"`), `data` may be absent and there's an `error` field. Persist `error` to `generated_lps.error_message`; set status to `ERROR`.

---

## Authentication

- Header: `api-key: <value>` (case-insensitive, FastAPI). Value from env var `LP_ASSISTANT_API_KEY`.
- Convention same as UG_EG.

---

## Retry behavior (service-side)

LP Assistant retries webhook delivery 3 times with exponential backoff (2, 4, 8s). dars must be idempotent by `job_id` (D-43).

---

## Subject + curriculum availability

- Grades 1–5 only.
- Subjects: Eng / Urdu / Maths / Science / GK.
- Curriculums: ICT (default), Punjab, Sindh.

If dars sends an unsupported combination, LP Assistant returns 400. Validate on our side first.

---

## What's NOT supported by LP Assistant today

- SLOs as inputs (we tag SLOs on our side post-process — D-22).
- Custom curriculums (Palestine, Tanzania) — Shujaan to add when needed.
- Dars Curriculum directly — for v1 we map DARS → ICT.

---

## Re-verifying this doc

If you suspect this doc is stale:

```bash
cd /home/hataf/taleemabad/UG_LessonPlan && git log -1 --format='%H %s' main
grep -n "VALID_LP_TYPES" config.py
grep -n "class LPGenerationRequest" main.py
```

If `VALID_LP_TYPES` differs from this doc, **update this doc first**, then revisit downstream code.
