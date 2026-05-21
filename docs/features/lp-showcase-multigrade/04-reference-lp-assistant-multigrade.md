# Reference — LP Assistant Multigrade Endpoint

Frozen snapshot of LP Assistant's multigrade contract as verified against `UG_LessonPlan` `main` at commit `4ec7b1d` on 2026-05-21. If the upstream changes, update this doc in the same PR as the generator change.

**Constants (from `UG_LessonPlan/config.py` and `services/multigrade_lp_service.py`):**
- `VALID_CURRICULUMS = ["ICT", "Punjab", "Sindh"]`
- `MG_VALID_SUBJECTS = ["Eng", "Maths", "Urdu"]`

---

## POST `/api/v1/generate-lp-multigrade`

**Auth:** `api-key` header (same key as the single-grade endpoints).

**Request body** (`MultigradeWebhookLPRequest`):

```jsonc
{
  "callback_url": "https://lp-assistant.taleemabad.com/api/webhook-status/placeholder",  // required, http(s)
  "curriculum": "ICT",                                  // default "ICT"; in VALID_CURRICULUMS
  "grades": [2, 3],                                     // required, 2..5 grades, each 1..5
  "subject": "Eng",                                     // Eng | Maths | Urdu (MG_VALID_SUBJECTS)
  "topic": "Journey through text",                      // optional
  "per_grade_page_numbers": {"2": "111", "3": "127-128"}, // OR per_grade_page_content
  "per_grade_page_content": null,                       // raw page text per grade, alternative to page_numbers
  "class_strength": 30,                                 // default 30
  "selected_model": null                                // optional override
}
```

**Validation (raises 400 otherwise):**
- `callback_url` must start with `http://` or `https://`.
- `curriculum` must be in `VALID_CURRICULUMS`.
- `grades` length 2..5, each int 1..5, deduplicated and sorted server-side.
- `subject` must be in `MG_VALID_SUBJECTS` (Eng / Maths / Urdu).
- Exactly one of `per_grade_page_numbers` or `per_grade_page_content` must be provided.

**Response (202 Accepted):**

```jsonc
{
  "status": "accepted",
  "job_id": "<uuid>",
  "callback_url": "<echoed>",
  "estimated_time_seconds": 90
}
```

The job runs in a `BackgroundTasks`; the server POSTs the final payload to `callback_url`. If polling instead of using a callback, see below.

---

## GET `/api/webhook-status/{job_id}`

**Auth:** `api-key` header.

**Response while running:**

```jsonc
{
  "status": "success",
  "job_id": "<uuid>",
  "job_status": "processing",      // or "pending", "completed", "failed"
  "created_at": "...",
  "updated_at": "...",
  "data": { /* RedisCache job document */ }
}
```

**Response when completed** — `data` is the full RedisCache job document. `RedisCache.save_response()` stores the multigrade payload under `data["response"]`, so the lesson plan lives at `data.response.lesson_plan`. **Important divergence from single-grade:** `lesson_plan` is a **parsed JSON dict**, not an HTML string (see `services/multigrade_lp_service.py` `_parse_lp_json`). The showcase generator renders this dict to HTML in Python — see D-7.

```jsonc
{
  "status": "success",
  "job_id": "<uuid>",
  "job_status": "completed",
  "data": {
    "status": "completed",
    "completed_at": "...",
    "updated_at": "...",
    "response": {
      "job_id": "<uuid>",
      "status": "completed",
      "lesson_plan": {
        "title": "<topic> — Multigrade Lesson (Grade X, Grade Y)",
        "grades": ["Grade X", "Grade Y"],
        "subject": "Eng",
        "total_duration": "60 minutes",
        "time_breakdown": "Opening 0–8 min | 2 rotations × 22 min | Closing 52–60 min",
        "slo_progression": { "Grade X": "<SLO>", "Grade Y": "<SLO>" },
        "resources": ["..."],
        "combined_opening": { "time": "0–8 min", "duration": "8 min", "title": "...", "steps": [{ "step": 1, "type": "Hook", "time": "...", "duration": "...", "instruction": "..." }, ...] },
        "board_prep": { "when": "...", "layout": "...", "sections": [{ "group_section": "Grade X", "heading": "...", "lines": ["..."], "prep_note": "..." }] },
        "rotations": [{ "rotation_number": 1, "time": "...", "duration": "...", "focus_group": "Grade X", "group_activities": { "Grade X": {"mode": "teacher", "task": "...", "board_instruction": "..."}, "Grade Y": {"mode": "independent", ...} }, "teacher_steps": [...], "transition_cue": {...} }, ...],
        "combined_closing": { "time": "...", "title": "...", "steps": [{ "type": "Share Out|Exit Ticket|Homework|Preview", "instruction": "...", "exit_tickets": {"Grade X": "...", "Grade Y": "..."}, "homework": {"Grade X": "...", "Grade Y": "..."} }] },
        "peer_tutoring_setup": "..."
      },
      "metadata": { "timings": {...}, "tokens": {...} }
    }
  }
}
```

The reference renderer for this shape is LP Assistant's own `displayMultigradeLessonPlan()` in `UG_LessonPlan/static/index.html` (~L2014–2400). The showcase generator's `render_multigrade_html()` is a Python port of that renderer.

**Failed jobs** — `save_error()` writes `data["status"] = "failed"` and `data["error"] = "<message>"`. There is no `data["response"]` on failure.

**404** if the job ID is unknown / expired.

---

## POST sink (no-op)

`POST /api/webhook-status/{job_id}` is a documented no-op (`200 ok`) and is what placeholder callback URLs target. Safe to use as `callback_url` when polling.

---

## Polling pattern for the generator

```python
poll_url = f"{base_url}/api/webhook-status/{job_id}"
for attempt in range(60):  # 5s × 60 = 5 minutes ceiling
    time.sleep(5)
    r = httpx.get(poll_url, headers={"api-key": api_key}, timeout=30)
    r.raise_for_status()
    body = r.json()
    job_status = body.get("job_status")
    if job_status == "completed":
        # RedisCache nests the multigrade payload under data.response
        return body["data"]["response"]["lesson_plan"]  # HTML
    if job_status == "failed":
        raise RuntimeError(body.get("data", {}).get("error", "unknown failure"))
    # else continue polling ("pending" or "processing")
raise TimeoutError(f"multigrade job {job_id} did not finish within 5 minutes")
```
