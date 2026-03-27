# Taleemabad — Company & Operations Context

## What Taleemabad does
Taleemabad is an edtech company that provides AI-powered teaching tools to schools in Pakistan. Core product is a curriculum-aligned lesson plan generator and related classroom tools.

## Teams relevant to Dars

### FDS (Forward Deployed Specialists) teams
- Go into regions (cities, districts) and work directly with teachers
- Goal: find product-market fit for Taleemabad tools in different contexts
- Often request lesson plans customized for their teachers — this is the primary demand driver for Dars
- They are the **B2B clients** that Dars serves

### Core / Platform team
- Maintains `taleemabad-core` (Django monolith) — the main product
- Dars is a standalone service that borrows LP generation infrastructure from here

## Parallel AI services (Taleemabad ecosystem)
These are separate services that may eventually integrate with Dars:

| Service | What it does | Relation to Dars |
|---|---|---|
| **LP Assistant** (`lp-assistant.taleemabad.com`) | Generates HTML lesson plans from curriculum metadata | Dars proxies it now; will absorb it in Phase 2 |
| **Digital Coach** | Records teacher lectures, gives feedback | Future: feedback informs LP personalization |
| **Exam Generation** | Generates exams; similar architecture to LP assistant | Potential future integration or shared infrastructure |
| **Teacher Training** | Generates training content for teachers | Future integration |

All of these follow a similar pattern: curriculum metadata in → AI-generated content out.

## LP Assistant service
- Lives at `lp-assistant.taleemabad.com`
- Codebase: `/home/hataf/taleemabad/UG_LessonPlan/`
- Generates HTML lesson plans from curriculum metadata (grade, subject, page number, etc.)
- Auth: `api-key` header (hardcoded shared secret)

### Key endpoints
| Endpoint | What it does |
|---|---|
| `POST /api/generate-lp` | Synchronous LP generation (~60s) |
| `POST /api/generate-lp-webhook` | Async LP generation with callback URL |
| `GET /api/webhook-status/{job_id}` | Poll async job status |
| `POST /api/edit-lp` | Edit an existing LP HTML given instructions |

### Generate LP request fields (key ones)
```json
{
  "curriculum": "ICT",         // "ICT" or "Punjab"
  "grade": 3,                  // integer
  "subject": "Maths",          // "Eng", "Urdu", "Maths", "Science"
  "page_number": "10",         // "5" or "5-7"
  "class_strength": 30,
  "exercise_page_number": "",  // optional
  "custom_prompt": "",         // optional override
  "generate_bilingual": false,
  "reasoning_enabled": true
}
```

### Generate LP response (key fields)
```json
{
  "status": "success",
  "lesson_plan": "<html>...</html>",
  "lesson_plan_bilingual": "<html>...</html>",
  "tags": { ... },
  "metadata": {
    "timings": { "total_time": 24.0 },
    "tokens": { "costs": { "total_usd": 0.35 } }
  }
}
```

## How taleemabad-core calls LP assistant
- File: `taleemabad_core/apps/lesson_plan/services/lp_assistant.py`
- Uses `requests.post()` (synchronous), 300s timeout
- Called from Celery background tasks (3 retries on 5xx)
- Validates input with `LPAssistantTagsSerializer` before sending

## Future data model considerations
- **Classes** — an FDS user creates a class, assigns teachers and students to it
- **Teachers / Students** — identity records; needed for personalization but NOT required for basic LP generation
- LP generation must remain usable without any teacher/student/class context — these are additive enrichments, not requirements
- Teacher priorities, trends, performance data (from Digital Coach) will eventually feed into LP personalization

## Vocabulary
- **LP** — Lesson Plan
- **FDS** — Forward Deployed Specialists (regional B2B clients)
- **ICT / Punjab** — curriculum types (ICT = national, Punjab = provincial)
- **Bilingual** — English + Urdu version of the lesson plan
- **Digital Coach** — lecture recording + feedback service
