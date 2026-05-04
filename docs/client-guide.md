# Dars Client Guide

**Audience:** AI agents and developers integrating with the Dars API.

Dars is Taleemabad's B2B service for curriculum-aligned lesson plan and exam generation. It exposes a REST API over HTTPS. All endpoints return JSON.

---

## Getting Started

1. Register your account at the Dars web app.
2. Go to **Settings** and select your curriculum (ICT or Punjab).
3. Your API key is shown in Settings — copy it and store it securely. It is shown only once and cannot be retrieved again.
4. Use the key to authenticate all API requests from your application.

---

## Authentication

Every request must carry your API key in the `X-API-Key` header.

```
X-API-Key: <your-api-key>
```

To rotate your key, call the rotate-key endpoint — the old key is invalidated immediately and the new one is returned once.

---

## Your Client Profile

`GET /api/v1/me` returns your current profile including `curriculum`, `name`, and `is_active`.

Your **curriculum** (`ICT` or `Punjab`) is set during registration via Settings. Most generation endpoints read it automatically — you never send it in a request body. If it is unset, generation endpoints will return a 422. You can update it at any time via `PATCH /api/v1/me`.

---

## Concepts

### external_id

Every generation endpoint accepts an optional `external_id` string. This is an opaque identifier you control — a teacher ID, student ID, coach ID, or any string meaningful to your system. Dars stores it and lets you filter listings by it. Dars never interprets or validates it.

### Async generation

Generation endpoints return **202 Accepted** immediately with `status: "PENDING"` and a record `id`. Generation runs in the background. Poll the individual GET endpoint for that record until `status` is `"READY"` or `"ERROR"`. A 3–5 second poll interval is appropriate. Generation typically completes in 30–120 seconds.

### Curriculum lock

Your contracted curriculum determines which grades and subjects are available. The following subjects and grades are supported per curriculum:

| Curriculum | Subjects | Grades |
|---|---|---|
| ICT | Eng, Maths, Urdu, Islamiat, GenSci (4–5), GenK (1–3), SST (4–5) | 1–5 |
| Punjab | Eng, Maths, Urdu | 1–5 |

---

## What You Can Do

### 1. Browse the Curriculum Tree

Get the full breakdown of your curriculum for a given grade and subject: chapters → topics → lessons. Each lesson includes the IDs of its pre-generated lesson plan and assessment (quiz), if they exist.

**Use this to:** build a table of contents, let a teacher navigate to a specific lesson, or resolve IDs before fetching content.

```
GET /api/v1/curriculum?grade=3&subject=Maths
```

Response shape:

```json
{
  "book_id": "...",
  "book_title": "...",
  "chapters": [
    {
      "id": "...",
      "chapter_number": 1,
      "title": "Numbers and Operations",
      "start_page": 1,
      "end_page": 24,
      "topics": [
        {
          "id": "...",
          "topic_number": 1,
          "title": "Addition",
          "start_page": 1,
          "end_page": 8,
          "lessons": [
            {
              "id": "...",
              "day_number": 1,
              "title": "Introduction to Addition",
              "lesson_plan_id": "...",   // null if not yet generated
              "assessment_id": "..."     // null if not yet generated
            }
          ]
        }
      ]
    }
  ]
}
```

Your curriculum is read from your profile; you do not send it.

---

### 2. Fetch a Pre-generated Lesson Plan

The curriculum tree contains `lesson_plan_id` values. Use these to fetch the actual HTML lesson plan content.

```
GET /api/v1/lesson-plans/{lesson_plan_id}
```

Lesson plans are **global** — any authenticated client can fetch any lesson plan by ID. There is no ownership check. The IDs are stable once generated.

Response includes `status`, `content` (HTML), `content_bilingual` (if generated), `grade`, `subject`, and `created_at`.

---

### 3. Fetch a Pre-generated Assessment (Teacher Quiz)

Assessments are linked to lesson plans. Fetch by the `assessment_id` from the curriculum tree.

```
GET /api/v1/assessments/{assessment_id}
```

Response includes `status`, `content_json` (structured question list), and `answers_json` (one answer per question). `content` (HTML) may be null — use `content_json` for structured access.

**Intended audience:** Teachers. These are 3-question MCQ quizzes designed to verify the teacher's own understanding of the lesson content before they deliver it — questions test comprehension and application, not trivial recall.

You can also trigger regeneration of the teacher assessment for any lesson plan:

```
POST /api/v1/lesson-plans/{lp_id}/assessment
```

Returns 201 with `status: "PENDING"`. Poll `GET /api/v1/assessments/{assessment_id}` until ready. Replaces any existing assessment for that lesson plan.

---

### 3b. Fetch a Pre-generated Student Assessment

**Intended audience:** Students. These are 5-question MCQ quizzes designed to check whether a student understood a lesson — questions focus on recall and straightforward comprehension.

Student assessments are generated on first fetch and persisted for all subsequent requests. Fetch by lesson plan ID:

```
GET /api/v1/lesson-plans/{lp_id}/student-assessment
```

If no student assessment exists yet, it is generated synchronously and returned in the same response — expect 10–15 seconds on first fetch. If one already exists (from a previous fetch by any client), it is returned immediately. If a previous generation was interrupted mid-flight, the next fetch will re-run generation automatically.

You can also fetch directly by assessment ID if you have it:

```
GET /api/v1/student-assessments/{assessment_id}
```

Response includes `status`, `content_json` (questions without answers), and `answers_json` (one answer + explanation per question).

---

### 4. Generate a Custom Lesson Plan

Generate a lesson plan for any page from your curriculum's textbook, outside the pre-built curriculum tree. Curriculum is taken from your profile.

```
POST /api/v1/custom-lesson-plans
```

Request body:

```json
{
  "grade": 3,
  "subject": "Maths",
  "page_number": "42",
  "topic": "Subtraction with borrowing",   // optional
  "class_strength": 30,                    // optional, defaults to 30
  "generate_bilingual": false,
  "external_id": "teacher-007"             // optional, your opaque ID
}
```

Returns 202 with a record containing `id` and `status: "PENDING"`. Poll `GET /api/v1/custom-lesson-plans/{id}` until ready.

Ready response adds `content` (HTML lesson plan) and optionally `content_bilingual`.

**List your custom LPs:**
```
GET /api/v1/custom-lesson-plans
GET /api/v1/custom-lesson-plans?external_id=teacher-007
```

---

### 5. Generate a Custom Exam

Generate an exam or class assessment for any page range from your curriculum's textbook.

```
POST /api/v1/custom-exam-generations
```

#### Parameters

| Field | Type | Required | Description |
|---|---|---|---|
| `grade` | integer | ✓ | Grade level. Values: `1`, `2`, `3`, `4`, `5` |
| `subject` | string | ✓ | Subject code. See subject table below. |
| `page_ranges` | string | ✓ | Pages or ranges from the textbook, e.g. `"1-5, 10, 15-20"` |
| `generation_type` | string | | `"exam"` (default) or `"class_assessment"` |
| `question_types` | array | ✓ | One or both of `"seen"` and `"unseen"` |
| `seen_categories` | array | | Required when `question_types` includes `"seen"`. One or both of `"objective"`, `"subjective"`. Seen questions are taken verbatim from the textbook pages — no AI invention. |
| `unseen_categories` | array | | Required when `question_types` includes `"unseen"`. One or both of `"objective"`, `"subjective"`. Unseen questions are freshly generated by the AI based on the topic, not lifted from the page. |
| `unseen_objective_types` | array | | Required when `unseen_categories` includes `"objective"`. Which objective question formats to generate. Subject-specific — see tables below. |
| `unseen_subjective_types` | array | | Required when `unseen_categories` includes `"subjective"`. Which subjective question formats to generate. Subject-specific — see tables below. |
| `unseen_objective_counts` | object | | How many questions per objective type, e.g. `{"MCQs": 5, "Fill in the Blanks": 4}`. Omit to use service defaults. |
| `unseen_subjective_counts` | object | | How many questions per subjective type, e.g. `{"Comprehension": 2, "Essay Writing": 1}`. Omit to use service defaults. |
| `long_question_sub_types` | array | | **Maths only.** Sub-types for `"Long Question"` when it appears in `unseen_subjective_types`. Values: `"Word Problems"`, `"Graphs & Geometric Problems"`. |
| `include_answer_key` | boolean | | Attach correct answers to every question in the output. Default: `false` |
| `image_generation_enabled` | boolean | | Auto-generate images for applicable question types. Default: `false` |
| `enable_review` | boolean | | Run an AI quality-review pass on the generated exam before returning. Adds latency (~30s). Default: `false` |
| `custom_system_prompt` | string | | Override the default system prompt sent to the AI. Use this to inject specific instructions, tone, difficulty level, formatting requirements, or language preferences. |
| `external_id` | string | | Your opaque identifier (teacher ID, student ID, session ID, etc.). Stored as-is and never interpreted. Use it to filter listings. |

#### Subject codes

| Code | Subject | Curricula | Grade restriction |
|---|---|---|---|
| `Eng` | English | ICT, Punjab | 1–5 |
| `Maths` | Mathematics | ICT, Punjab | 1–5 |
| `Urdu` | Urdu | ICT, Punjab | 1–5 |
| `Islamiat` | Islamiat | ICT | 1–5 |
| `GenSci` | General Science | ICT | 4–5 only |
| `GenK` | General Knowledge | ICT | 1–3 only |
| `SST` | Social Studies | ICT | 4–5 only |

#### Objective question types

**English / Urdu / Islamiat / GenSci / GenK / SST:**

`MCQs`, `MSQs`, `Fill in the Blanks`, `Missing Letters`, `True/False`, `Match Columns`, `Circle the Correct`, `Rewrite Sentences`, `Brief Answers`, `Listening`, `Speaking`, `Reading`

**Maths:**

`MCQs`, `MSQs`, `Fill in the Blanks`, `True/False`, `Match Columns`, `Mental Math`, `Missing Gaps`, `Sequences`

#### Subjective question types

**English / Urdu / Islamiat / GenSci / GenK / SST:**

`Word Meanings`, `Word Sentences`, `Comprehension`, `Rewriting`, `Story Completion`, `Simple Writing`, `Formal Letter`, `Informal Letter`, `Application Writing`, `Story Writing`, `Essay Writing`, `Paragraph Writing`, `Picture Description`, `Project Work`, `Brief Answers`, `Mind Map`, `Label the Diagram`, `Flow Chart`, `Logical Reasoning`

**Maths:**

`Short Questions`, `Restricted Questions`, `Long Question`

> When `Long Question` is selected for Maths, you may also pass `long_question_sub_types`: `"Word Problems"` and/or `"Graphs & Geometric Problems"`.

#### Example — English exam, seen + unseen

```json
{
  "grade": 4,
  "subject": "Eng",
  "page_ranges": "10-15",
  "generation_type": "exam",
  "question_types": ["seen", "unseen"],
  "seen_categories": ["objective", "subjective"],
  "unseen_categories": ["objective", "subjective"],
  "unseen_objective_types": ["MCQs", "Fill in the Blanks", "True/False"],
  "unseen_subjective_types": ["Word Meanings", "Essay Writing"],
  "unseen_objective_counts": { "MCQs": 5, "Fill in the Blanks": 4, "True/False": 5 },
  "unseen_subjective_counts": { "Word Meanings": 1, "Essay Writing": 1 },
  "include_answer_key": true,
  "external_id": "coach-99"
}
```

#### Example — Maths class assessment, unseen only

```json
{
  "grade": 3,
  "subject": "Maths",
  "page_ranges": "5-12",
  "generation_type": "class_assessment",
  "question_types": ["unseen"],
  "unseen_categories": ["objective", "subjective"],
  "unseen_objective_types": ["MCQs", "Fill in the Blanks"],
  "unseen_subjective_types": ["Short Questions", "Long Question"],
  "unseen_objective_counts": { "MCQs": 5, "Fill in the Blanks": 5 },
  "unseen_subjective_counts": { "Short Questions": 4, "Long Question": 2 },
  "long_question_sub_types": ["Word Problems"],
  "include_answer_key": false
}
```

Returns 202 with `id` and `status: "PENDING"`. Poll `GET /api/v1/custom-exam-generations/{id}` until ready.

#### Ready response — `result` structure

When `status` is `"READY"`, the `result` field contains the full output from the generation service:

```
result.response.exam_json     structured exam content (see below)
result.response.exam_paper    full HTML string, ready to render
result.response.metadata      tokens used, cost, timings
```

`exam_json` is organised by section and question type:

```json
{
  "seen": {
    "objective": {
      "MCQs": [...],
      "Fill in the blanks": [...],
      "True/False": [...],
      "Match the Column": [...]
    },
    "subjective": {
      "Brief Answers": [...],
      "Simple Writing": [...]
    }
  },
  "unseen": { ... }
}
```

Each question object contains:

| Field | Description |
|---|---|
| `question` | The question text |
| `main_question` | Section/group header (e.g. "Choose the correct option") |
| `answer` | Correct answer — **always present**, regardless of `include_answer_key` |
| `marks` | Mark allocation |
| `lines` | Suggested answer lines (0 for objective) |
| `blooms` | Bloom's taxonomy level (Remember, Understand, Apply, Analyze, Evaluate) |
| `options` | MCQ options object `{"a": ..., "b": ..., "c": ..., "d": ...}` (MCQs only) |

> **Note on `include_answer_key`:** This flag controls whether answers appear in the rendered `exam_paper` HTML — it does not affect `exam_json`. The `answer` field is always present in the JSON. If you want to show a student-facing exam without answers, use `exam_json` and omit the `answer` field when rendering.

#### Example — full request and response

**Request:**
```json
{
  "grade": 4,
  "subject": "Eng",
  "page_ranges": "10-15",
  "generation_type": "exam",
  "question_types": ["seen", "unseen"],
  "seen_categories": ["objective", "subjective"],
  "unseen_categories": ["objective", "subjective"],
  "unseen_objective_types": ["MCQs", "Fill in the Blanks", "True/False"],
  "unseen_subjective_types": ["Word Meanings", "Essay Writing"],
  "unseen_objective_counts": { "MCQs": 5, "Fill in the Blanks": 4, "True/False": 5 },
  "unseen_subjective_counts": { "Word Meanings": 1, "Essay Writing": 1 },
  "include_answer_key": true,
  "external_id": "doc-example"
}
```

**Response (202 on submit, then poll until READY):**
```json
{
  "id": "d9a37488-e8b8-4d10-8762-fd634c6e2b72",
  "client_id": "...",
  "status": "READY",
  "curriculum": "Punjab",
  "grade": 4,
  "subject": "Eng",
  "page_ranges": "10-15",
  "generation_type": "exam",
  "external_id": "doc-example",
  "error_detail": null,
  "created_at": "2026-05-04T08:54:34Z",
  "updated_at": "2026-05-04T09:01:12Z",
  "result": {
    "status": "completed",
    "request": { "...echo of request body..." },
    "response": {
      "status": "success",
      "job_id": "...",
      "tags": {
        "grade": 4,
        "subject": "Eng",
        "curriculum": "Punjab",
        "page_ranges": "10-15",
        "total_pages": 6,
        "parsed_pages": [10, 11, 12, 13, 14, 15],
        "question_types": ["seen", "unseen"]
      },
      "metadata": {
        "tokens": { "input_tokens": 8297, "output_tokens": 8969, "total_tokens": 17266, "cost_usd": 0.124 },
        "timings": { "db_fetch_book_text": 2.5, "exam_generation": 148.6, "total_time": 151.2 },
        "total_cost_usd": 0.124
      },
      "exam_json": {
        "seen": {
          "objective": {
            "Fill in the blanks": [
              {
                "question": "______ man who wrote this book is famous.",
                "main_question": "Fill in the blanks with 'a', 'an' or 'the'.",
                "answer": "The",
                "marks": 1,
                "lines": 0,
                "blooms": "Apply"
              }
            ]
          },
          "subjective": {
            "Rewrite": [
              {
                "question": "peshawar, lahore, quetta and karachi are the most famous cities of pakistan.",
                "main_question": "Rewrite the given sentences with correct capitalisation.",
                "answer": "Peshawar, Lahore, Quetta and Karachi are the most famous cities of Pakistan.",
                "marks": 2,
                "lines": 2,
                "blooms": "Apply"
              }
            ],
            "Paragraph Writing": [
              {
                "question": "Write a paragraph about Hazrat Muhammad (ﷺ). Look at the given mind map.",
                "main_question": "Write a paragraph",
                "answer": "Hazrat Muhammad (ﷺ) is the last prophet of Allah...",
                "marks": 5,
                "lines": 8,
                "blooms": "Create",
                "image": "https://ug-ai-gen-images.s3.amazonaws.com/..."
              }
            ]
          }
        },
        "unseen": {
          "objective": {
            "MCQs": [
              {
                "question": "Which article should be used: I saw ___ elephant at the zoo.",
                "main_question": "Choose the correct option",
                "options": ["a) a", "b) an", "c) the", "d) none"],
                "answer": "b) an",
                "marks": 1,
                "lines": 0,
                "blooms": "Apply"
              }
            ],
            "True/False": [
              {
                "question": "The word 'an' is used before words starting with a consonant sound.",
                "main_question": "Write True or False",
                "answer": "False",
                "marks": 1,
                "lines": 0,
                "blooms": "Remember"
              }
            ],
            "Fill in the blanks": [
              {
                "question": "She is wearing a ___________ dress.",
                "main_question": "Fill in the blanks with the correct word (Word Bank: beautiful, an, the, Pakistani)",
                "answer": "beautiful",
                "marks": 1,
                "lines": 0,
                "blooms": "Apply"
              }
            ]
          },
          "subjective": {
            "Word Meanings": [
              {
                "main_question": "Write the meanings of the given words",
                "words": ["famous", "naughty", "costly", "similar"],
                "answer": "famous: known by many people\nnaughty: behaving badly\ncostly: expensive\nsimilar: almost the same",
                "marks": 4,
                "lines": 4,
                "blooms": "Remember"
              }
            ],
            "Essay Writing": [
              {
                "question": "Write an essay on the topic: 'The Beauty of Nature'.",
                "main_question": "Write an essay",
                "answer": "Nature is a beautiful gift to us...",
                "marks": 10,
                "lines": 15,
                "blooms": "Create"
              }
            ]
          }
        }
      },
      "exam_paper": "<div class=\"exam-paper\">...full rendered HTML...</div>",
      "page_content": "=== Page 10 ===\n...raw OCR text from textbook pages..."
    }
  }
}
```

> **Note:** MCQ `options` come back as an array of strings (`["a) ...", "b) ..."]`), not an object. Word Meanings questions have a `words` array instead of a `question` string. Some subjective questions include an `image` URL for picture-based prompts.

**List your custom exams:**
```
GET /api/v1/custom-exam-generations
GET /api/v1/custom-exam-generations?external_id=coach-99
```

---

### 6. Analytics

Get aggregate counts for your account's custom lesson plans and exam generations.

```
GET /api/v1/analytics
```

Response:

```json
{
  "lesson_plans": {
    "total": 120,
    "by_status": { "pending": 2, "ready": 115, "error": 3 },
    "by_subject": [{ "subject": "Maths", "count": 60 }, ...],
    "by_grade": [{ "grade": "3", "count": 40 }, ...],
    "daily_last_30": [{ "date": "2026-04-15", "count": 5 }, ...]
  },
  "exam_generations": { ... }
}
```

---

## Status Values

All generation records use the same three statuses:

| Status | Meaning |
|---|---|
| `PENDING` | Queued, not yet started or in progress |
| `READY` | Completed successfully — content fields are populated |
| `ERROR` | Generation failed — check `error_detail` for reason |

---

## Error Responses

| Code | Meaning |
|---|---|
| 401 | Missing or invalid API key |
| 404 | Record not found (or not owned by your client) |
| 422 | Validation error — check `detail` field; common cause is no curriculum set |
| 500 | Server error — retry with backoff |

Error bodies follow FastAPI's standard shape:
```json
{ "detail": "human-readable reason" }
```

---

## API Reference

> **Note:** The endpoint paths below are accurate as of the time this document was written but are subject to change. Treat this as a starting point; verify against the live `/docs` (Swagger UI) or `/redoc` endpoints on the server.

### Account

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/me` | Your client profile |
| PATCH | `/api/v1/me` | Update curriculum |
| POST | `/api/v1/me/rotate-key` | Rotate API key |

### Curriculum

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/curriculum` | Full curriculum tree for a grade+subject (`?grade=&subject=`) |
| GET | `/api/v1/books` | List books (filterable by curriculum, grade, subject) |
| GET | `/api/v1/books/{id}/chapters` | List chapters for a book |
| GET | `/api/v1/books/{id}/stats` | Generation coverage stats for a book |

### Pre-generated Content

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/lesson-plans/{id}` | Fetch a lesson plan by ID |
| GET | `/api/v1/lesson-plans` | List all lesson plans (global) |
| GET | `/api/v1/assessments/{id}` | Fetch a teacher assessment by ID |
| POST | `/api/v1/lesson-plans/{id}/assessment` | Generate (or regenerate) teacher assessment for an LP |
| GET | `/api/v1/lesson-plans/{id}/student-assessment` | Fetch student assessment for an LP (generates on first fetch) |
| GET | `/api/v1/student-assessments/{id}` | Fetch a student assessment by ID |

### Custom Lesson Plans

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/custom-lesson-plans` | Queue a custom lesson plan |
| GET | `/api/v1/custom-lesson-plans` | List yours (`?external_id=` to filter) |
| GET | `/api/v1/custom-lesson-plans/{id}` | Get a single custom lesson plan |

### Custom Exam Generations

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/custom-exam-generations` | Queue a custom exam |
| GET | `/api/v1/custom-exam-generations` | List yours (`?external_id=` to filter) |
| GET | `/api/v1/custom-exam-generations/{id}` | Get a single custom exam generation |

### Analytics

| Method | Path | Description |
|---|---|---|
| GET | `/api/v1/analytics` | Aggregate stats for your custom LPs and exams |

---

## Typical Integration Flow

```
1. GET /api/v1/me
   → confirm curriculum is set; if not, PATCH /api/v1/me first

2. GET /api/v1/curriculum?grade=3&subject=Maths
   → build your navigation tree
   → collect lesson_plan_id and assessment_id for each lesson

3. GET /api/v1/lesson-plans/{lesson_plan_id}
   → render HTML to the teacher/student

4. POST /api/v1/custom-exam-generations   (when teacher wants a fresh exam)
   → store returned id
   → poll GET /api/v1/custom-exam-generations/{id} every 5s
   → when status == "READY", use result

5. GET /api/v1/analytics
   → periodic reporting to your own dashboard
```
