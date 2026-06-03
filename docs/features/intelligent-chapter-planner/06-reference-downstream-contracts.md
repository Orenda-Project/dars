# Reference — Downstream Contracts (frozen)

What each PlanItem becomes when dispatched. The planner does NOT call these directly — the existing generation layer does (`generated_lps/`, `generated_exams/`, `router_generation.py`). This doc records the seam so the plan's outputs are known-compatible. Authoritative copies: `docs/plans/2026-05-15-dars-v2-rebuild/08-reference-lp-assistant-api.md` and `09-reference-ug-eg-api.md`.

## LP unit → LP Assistant v3 (`POST /api/v3/generate-lp`)

Built by `generated_lps/lp_assistant_client.LPRequest` → `_build_body`. Fields the planner's output feeds:

| LPRequest field | Source from a PlanItem (LP unit) |
|---|---|
| `curriculum_code` | CST's curriculum (resolved upstream; mapped via D-61) |
| `grade` | CST grade |
| `subject` | CST subject (Eng/Urdu/Maths/Science/GK) |
| `page_content` | **concat of the unit's topics' `topic_text` in order** (multi-topic merge, D-2) |
| `lp_type` | the unit's `lp_type` (validated `is_valid_lp_type`) |
| `sub_slo_statements` | the `statement`s of the unit's `sub_slo_ids` → becomes `custom_prompt` (D-1 of lp-slo-injection feature) |
| `callback_url` | existing webhook URL |
| `class_strength`, `generate_bilingual` | existing defaults |

Returns `202` + `job_id`; content arrives via webhook (F3.6). Multi-topic units route through the **class-scope** cache branch (D-9) so they don't collide with single-topic global cache entries.

## FA item → UG_EG v2 (`POST /api/v2/generate-exam`)

Built by `generated_exams/ug_eg_client.ExamRequest` + `generated_exams/service.build_question_config`. Fields:

| ExamRequest field | Source |
|---|---|
| `curriculum_code`, `grade`, `subject` | CST context |
| `page_content` | concat of the FA item's `topic_ids`' `topic_text` |
| `generation_type` | `"class_assessment"` |
| `question_types` / `unseen_*` | `DEFAULT_FA_CONFIG[subject]` from `generated_lps/batch_service.py` (per-subject FA defaults, D-46). This round keeps the static FA config — the planner chooses *coverage* (which sub-SLOs/topics), not question mix. |
| `include_answer_key` | `True` |
| `callback_url` | existing webhook |

Returns `202` + `job_id`; exam + answer key + question→sub-SLO tags arrive via webhook (F3.6).

## What this feature does NOT change

- The webhook processors, the cache tables (`generated_lps`, `generated_exams`), the tagging services, and the question-config defaults are all reused unchanged. The only new thing flowing through is **multi-topic `page_content`** and **planner-chosen sub-SLO coverage** — both already expressible in the existing request shapes.
