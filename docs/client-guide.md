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

### 3. Fetch a Pre-generated Assessment (Quiz)

Assessments are linked to lesson plans. Fetch by the `assessment_id` from the curriculum tree.

```
GET /api/v1/assessments/{assessment_id}
```

Response includes `status`, `content_json` (structured question list), and `answers_json` (one answer per question). `content` (HTML) may be null — use `content_json` for structured access.

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

Request body (all optional fields can be omitted):

```json
{
  "grade": 4,
  "subject": "Eng",
  "page_ranges": "10-15, 20",
  "generation_type": "exam",              // "exam" | "class_assessment"
  "question_types": ["seen", "unseen"],   // one or both
  "seen_categories": ["objective", "subjective"],
  "unseen_categories": ["objective", "subjective"],
  "unseen_objective_types": ["MCQs", "Fill in the Blanks"],
  "unseen_subjective_types": ["Comprehension"],
  "unseen_objective_counts": { "MCQs": 5 },
  "unseen_subjective_counts": { "Comprehension": 2 },
  "long_question_sub_types": [],          // Maths only: ["Word Problems", "Graphs & Geometric Problems"]
  "include_answer_key": false,
  "image_generation_enabled": false,
  "enable_review": false,
  "external_id": "coach-99"              // optional
}
```

Returns 202 with `id` and `status: "PENDING"`. Poll `GET /api/v1/custom-exam-generations/{id}` until ready.

Ready response adds `result` (full exam JSON from the generation service).

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
| GET | `/api/v1/assessments/{id}` | Fetch an assessment by ID |

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
