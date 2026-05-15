---
type: plan
last_verified: 2026-05-15
owner: hataf
---

# Plan: LP Showcase — pre-generate 10 LPs straight from LP Assistant for Ali Sipra review

## What this does

Generates 10 specific lesson plans (5 Grade 2 + 5 Grade 5, English) by calling LP Assistant's `/api/generate-lp` directly, stores the returned HTML as static files inside the Dars webapp, and serves them at a clean shareable URL (`/showcase/ali-sipra-2026-05-15`) where the user can review all 10 side-by-side and forward the link to Ali Sipra.

Dars backend, Dars DB, Dars API key flow, curriculum config — none of it touched. Pure LP-Assistant-to-static-HTML pipeline.

## Why

Forwarded ask: stakeholder wants 10 LPs generated **today** for review. The user clarified: *"no curriculum needed, we just want to showcase the LPs made from LP Assistant directly."* So we skip Dars entirely — no client provisioning, no `external_id` plumbing, no async queue. Just hit LP Assistant, save the HTML, serve it.

## What changes

### Backend
None.

### Frontend (Dars webapp — used only as the static host)
- **New static directory**: `webapp/public/showcase/ali-sipra-2026-05-15/`
  - `index.json` — array of `{id, grade, skill, page, topic, status, html_file, error?}` describing the 10 LPs (written by the trigger script)
  - `lp-01.html`, `lp-02.html`, … `lp-10.html` — raw HTML returned by LP Assistant (written by the trigger script)
- **New route**: `webapp/app/showcase/[tag]/page.tsx`
  - Public (no auth) — reads `public/showcase/<tag>/index.json` at request time via Node `fs`
  - Renders a two-pane layout: left = clickable list of all 10 LPs (Grade, skill, page, status badge); right = selected LP's HTML loaded from `/showcase/<tag>/lp-XX.html` (iframe or `dangerouslySetInnerHTML` after `fetch`)
  - First LP selected by default
  - Read-only. URL itself is the share link.

That's it for the webapp.

### Trigger script
- **New script**: `useful-scripts/generate_showcase_lps.py`
  - Hardcoded list of 10 LP specs (the inputs the stakeholder gave)
  - Reads `LP_ASSISTANT_URL` (default `https://lp-assistant.taleemabad.com`) and `LP_ASSISTANT_API_KEY` from env — the shared secret used by Dars also works here
  - Curriculum: defaults to `"ICT"` — that's the national/federal English textbook set and the most common fit for "page 111 / journey through text"-style content. Override via `--curriculum Punjab|Sindh|ICT` flag if first-round results look wrong
  - For each spec: POSTs to `/api/generate-lp` with `grade`, `subject="English"`, `page_number`, `class_strength=30`, `generate_bilingual=false`, `reasoning_enabled=true`
  - Writes each response's `lesson_plan` HTML to `webapp/public/showcase/<tag>/lp-NN.html`
  - Writes summary `index.json`
  - Re-runnable: clears the target directory on start, regenerates fresh. Errors are captured in `index.json` with `status:"ERROR"` and `error` text so the showcase view shows them
  - Runs the 10 requests with a small concurrency limit (3) since each LP takes ~60s — total wall time ~3–4 min

### DB / migrations / tests
None.

## Bead
- ID: `feat-lp-showcase`
- Title: LP showcase static view + LP Assistant trigger script for Ali Sipra review
- Category: feature

## The 10 LP specs

All English, default `curriculum="ICT"`, `class_strength=30`, `generate_bilingual=false`, `reasoning_enabled=true`.

### Grade 2
| # | Skill | Page | Topic (passed as custom_prompt context) |
|---|---|---|---|
| 1 | Reading | 111 | Journey through text |
| 2 | Comprehension w/ meanings | 15 | New words to know |
| 3 | Comprehension Q&A | 127,128 | Activity 2 |
| 4 | Grammar | 10 | Activity 3 |
| 5 | Creative writing | 133 | — |

### Grade 5
| # | Skill | Page | Topic |
|---|---|---|---|
| 6 | Reading | 32,33 | Journey through text |
| 7 | Comprehension w/ meanings | 44,45 | Memory lane |
| 8 | Comprehension Q&A | 49 | Activity 3 |
| 9 | Grammar | 39 | Activity 3 |
| 10 | Creative writing | 15 | Activity 3 |

LP Assistant doesn't take a structured "skill" or "topic" field for the page-based endpoint, so:
- We pass `custom_prompt = f"Focus this lesson on the {skill} skill. Topic: {topic_label}."` so the generator biases output toward that skill area
- The skill/topic labels are also stored in `index.json` and displayed in the list pane regardless of what's inside the HTML

## Risks & constraints

- **OCR coverage** — LP Assistant fetches book text from its DB by `(curriculum, grade, subject)` → `book_id`. If a given page isn't OCR'd in the configured curriculum, the response will be 404 or empty. Risk for Grade 2 English ICT page 111: real, since 111 is deep into the book. We capture per-LP errors in `index.json` and surface them in the UI so failures are visible immediately, then retry with `--curriculum Punjab` (or Sindh) if ICT misses.
- **No bilingual on first pass** — English-only review first; bilingual re-run is one flag flip if requested.
- **Static files in `public/`** — these get committed to git unless we gitignore `webapp/public/showcase/`. Decision: **gitignore the showcase directory**. The output is regeneratable and the LPs may contain rough or pre-review content not meant for the repo. The plan adds `webapp/public/showcase/` to `webapp/.gitignore`.
- **Sharing** — the share link is whatever the webapp's deployed URL is (e.g. `https://app.dars.taleemabad.com/showcase/ali-sipra-2026-05-15`). For local-only review before that, `http://localhost:3000/showcase/ali-sipra-2026-05-15` works during `npm run dev`. We need to actually deploy/push for Ali Sipra to see it; flagged for confirmation at hand-off.
- **LP Assistant API key** — needs to be in env when running the script. If not set, the script fails fast with a clear message.

## E2E test scenarios

- Run the script end-to-end against staging LP Assistant; 10 HTML files + `index.json` appear in `webapp/public/showcase/ali-sipra-2026-05-15/`
- Visit `http://localhost:3000/showcase/ali-sipra-2026-05-15` — list shows 10 entries with statuses; first LP renders by default
- Click each LP — right pane swaps to that LP's HTML
- Visit the URL on a fresh browser session (incognito, no localStorage) — no auth prompt, page renders identically (public route)
- If one LP failed: its row shows ERROR badge + the error message, doesn't crash the view
