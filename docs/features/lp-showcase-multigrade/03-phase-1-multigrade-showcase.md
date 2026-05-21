# Phase 1 — Multi-grade LPs in the showcase

**Bead:** `feat-lp-showcase-multigrade-phase-1`
**PR target:** `staging`
**Independently shippable:** yes — one PR, ships the full feature.

Five numbered features. F-1.1 → F-1.2 → F-1.3 are sequential (data → script → frontend); F-1.4 and F-1.5 are wiring/test.

---

## F-1.1 — Widen `LPSpec.grade` and `index.json` `grade` field

**Spec.** Change `LPSpec.grade` in `useful-scripts/generate_showcase_lps.py` from `int` to `int | list[int]`. Update `write_results()` so `entry["grade"]` writes either a number or a list of numbers to `index.json`. Update `wrap_html()` so the printed heading shows either "Grade {N} — {skill}" (existing) or "Grades {labels} — {skill}" where `labels` is e.g. "2–3" for contiguous or "1, 3, 5" for non-contiguous. The HTML title and any visible grade strings must match.

**Acceptance.**
- `LPSpec(grade=[2, 3])` validates and round-trips through `write_results()`.
- A multi-grade entry in `index.json` looks like `{"id": 11, "grade": [2, 3], ...}`.
- A multi-grade LP's wrapped HTML `<title>` reads `Grades 2–3 — Reading` (or the right label for the spec).

**Dependencies.** None.

---

## F-1.2 — Generator path for `/api/v1/generate-lp-multigrade`

**Spec.** Add a sibling function `generate_one_multigrade(spec, base_url, api_key, curriculum)` in `generate_showcase_lps.py` that:

1. POSTs to `{base_url}/api/v1/generate-lp-multigrade` with the body in [04-reference-lp-assistant-multigrade.md](04-reference-lp-assistant-multigrade.md). `callback_url` is a placeholder pointing at the same host's `/api/webhook-status/<placeholder>` POST sink (D-4). `grades` is `spec.grade` (a `list[int]`). `subject="Eng"`, `class_strength=30`, `curriculum=<arg>`. `per_grade_page_numbers` must be a `{"<grade_int_as_str>": "<page_string>"}` dict, populated from `spec.per_grade_pages` (new field on `LPSpec`, see below).
2. On 202 Accepted, extracts `job_id` and polls `GET {base_url}/api/webhook-status/{job_id}` every 5 seconds, with a 5-minute (60 attempt) ceiling.
3. Terminal status: when polled response shows `body.job_status == "completed"` and `body.data.response.lesson_plan` (HTML string) is non-empty, return `LPResult(spec, "OK", html=...)`. When `body.job_status == "failed"` (read error from `body.data.error`) or status code 5xx, return `LPResult(spec, "ERROR", error=...)`. See [04-reference-lp-assistant-multigrade.md](04-reference-lp-assistant-multigrade.md) for the full polled response shape — note that `RedisCache.save_response()` nests the payload under `data["response"]`, not directly on `data`.
4. Never raises — same contract as `generate_one()`.

Extend `LPSpec` with `per_grade_pages: dict[int, str] | None = None`. Existing single-grade entries leave it `None`. Multi-grade entries fill it.

Add a small dispatcher in `main()` (or in the per-spec submission): if `isinstance(spec.grade, list)`, submit to `generate_one_multigrade`; else `generate_one`.

**Acceptance.**
- A multi-grade `LPSpec` with `grade=[2, 3]` and `per_grade_pages={2: "111", 3: "127-128"}` produces an HTML file on disk after running the script.
- The polling loop emits an INFO log per attempt with attempt number and observed job status.
- A failed job (mocked or genuine) yields `status: "ERROR"` in `index.json` and the error message in `entry["error"]`.

**Dependencies.** F-1.1 (the `grade` field must accept a list).

---

## F-1.3 — Skip review for multi-grade entries

**Spec.** In `run_reviews()` and `write_results()`:

- `write_results()` for any entry where `r.spec.grade` is a list: set `review_status="MISSING"`, `review_error="no multi-grade reviewer available"`, do **not** write a stub `.review.json` file (or write an empty stub — pick one and be consistent).
- `run_reviews()` (the `--reviews-only` path): when iterating entries, skip any whose `entry["grade"]` is a list. Mark them `review_status="MISSING"`, `review_error="no multi-grade reviewer available"`. Do not enqueue them for `/api/review-lp`.

**Acceptance.**
- A multi-grade entry in `index.json` has `review_status: "MISSING"` and `review_error: "no multi-grade reviewer available"`.
- `--reviews-only` does not POST to `/api/review-lp` for any multi-grade entry.

**Dependencies.** F-1.1.

---

## F-1.4 — Frontend: extend `ShowcaseEntry` and group multi-grade

**Spec.** In `webapp/components/templates/showcase-template.tsx`:

- Widen `ShowcaseEntry.grade` from `number` to `number | number[]`.
- In the `grouped` `useMemo`: bucket entries with `Array.isArray(grade)` into a `"Multi-Grade"` group keyed by a sentinel (e.g. `-1` for sort order — multi-grade always last). The group's `items` are sorted by `id` (same as numeric groups).
- Sidebar group header: for the multi-grade group, show "Multi-Grade" as the label and a subtitle like "G{min}–G{max}" if contiguous, else "G{a}, G{b}, …". Match the visual weight of the existing grade labels — don't add a banner.
- Main-pane header (the `Grade {selected.grade} · {selected.skill}` line): render "Grades {labels} · {selected.skill}" when `Array.isArray(selected.grade)`.
- The grouping order: ascending numeric grades first (2, 5, …), then "Multi-Grade" last.
- Update `loadShowcase()` in `webapp/app/showcase/[tag]/page.tsx` if any tighter typing in `ShowcaseEntry` requires touching it — should be type-only.

**Acceptance.**
- The page at `/showcase/lp-showcase` shows three sidebar groups: Grade 2, Grade 5, Multi-Grade.
- Selecting a multi-grade entry shows "Grades 2–3 · Reading" (or appropriate label) in the main-pane header.
- The ReviewDrawer renders nothing for multi-grade entries (review_status is MISSING, falls through to the existing null-render path).

**Dependencies.** F-1.1 (data shape must already widen), F-1.2 (real entries must exist to test against; or hand-edit `index.json` for frontend-first dev).

---

## F-1.5 — Seed: add 2–3 multi-grade `LPSpec` entries and regenerate

**Spec.** Append the following to `SPECS` in `generate_showcase_lps.py`:

```python
LPSpec(11, [2, 3], "Reading", "p. 111 / p. 127–128", "Journey through text", "multigrade",
       per_grade_pages={2: "111", 3: "127-128"}),
LPSpec(12, [4, 5], "Comprehension Q&A", "p. 30 / p. 49", "Activity 3", "multigrade",
       per_grade_pages={4: "30", 5: "49"}),
# Optional third — keep if generation budget allows on the first run:
LPSpec(13, [1, 2, 3, 4, 5], "Creative writing", "various", "Memory lane", "multigrade",
       per_grade_pages={1: "10", 2: "133", 3: "32", 4: "39", 5: "15"}),
```

The exact `page` strings are display-only (shown in the sidebar subtitle); the **real** page numbers fed to LP Assistant come from `per_grade_pages`. Topic names should mirror the existing single-grade entries' topic style.

After adding the specs, run:

```
LP_ASSISTANT_API_KEY=... python3 useful-scripts/generate_showcase_lps.py
```

This regenerates everything under `webapp/public/showcase/lp-showcase/` (the script `reset_output_dir`s, so single-grade LPs are re-generated too — cost trade-off the user has accepted before).

**Acceptance.**
- `webapp/public/showcase/lp-showcase/index.json` contains entries 11, 12 (and optionally 13), each with `grade` as a list.
- `lp-11.html`, `lp-12.html` exist and render as styled lesson plan HTML.
- The frontend at `/showcase/lp-showcase` shows the new "Multi-Grade" group containing 2 (or 3) entries.

**Dependencies.** F-1.1, F-1.2, F-1.3, F-1.4 all merged or in the same PR.

---

## Notes from execution

### 2026-05-21 — Multigrade response is JSON, not HTML (D-7)

When F-1.5 first ran, both successful multigrade jobs returned `lesson_plan` as a parsed JSON dict, not the HTML string that single-grade returns. ID 13 (G1–G5 Creative writing) failed upstream during LP Assistant's own JSON post-processing (`Expecting value: line 765 column 1`) — a real generation failure, unrelated to this code path.

**Resolution:** added D-7. Added a `render_multigrade_html()` function to `generate_showcase_lps.py` that ports `UG_LessonPlan/static/index.html` `displayMultigradeLessonPlan` to Python, emitting Dars-styled HTML (uses the existing `<body class="lp-doc">` shell and `/showcase/_assets/lp.css` so iframe display is unchanged). `generate_one_multigrade()` runs the response through the renderer before returning `LPResult.html`.

For ID 13's upstream failure, the path forward is either to retry or to drop the spec; the script's existing error-handling already records it as `status: "ERROR"` with the message in `index.json`, so the page handles it gracefully via the existing ERROR fallback view.
