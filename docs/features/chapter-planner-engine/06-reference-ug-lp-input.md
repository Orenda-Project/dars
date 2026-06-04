# Reference — UG_LessonPlan `/generate-lp` input (frozen)

CPE's output Plan Units must map losslessly onto this shape (D-7). Copied from
`UG_LessonPlan/main.py::LPGenerationRequest` and `config.py::VALID_LP_TYPES` as of 2026-06-03. If
UG_LP changes, update this doc; do not leave the plan to re-read UG_LP source mid-execution.

## `LPGenerationRequest` (relevant fields)

```python
class LPGenerationRequest(BaseModel):
    curriculum: str = "ICT"          # "ICT" | "Punjab" | (Sindh)
    grade: int                       # 1..5
    subject: str                     # see VALID_LP_TYPES keys
    page_number: Optional[str] = None     # OR page_content; one required
    page_content: Optional[str] = None    # supply content directly; skips DB  ← we use this
    lp_type: Optional[str] = None         # skill-based; must ∈ VALID_LP_TYPES[subject]
    class_strength: Optional[int] = 30
    # … other optional fields (bilingual, review, images, model) default off; CPE leaves unset
```

Endpoint: `POST /api/v3/generate-lp` (async, webhook) or the sync variants. CPE only documents the
request shape — it does not call UG_LP in v2 (D-7 / Phase 3 adapter shows the mapping only).

## `VALID_LP_TYPES` (per subject)

```python
VALID_LP_TYPES = {
    "Eng":      ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Urdu":     ["reading", "comprehension_word_meanings", "comprehension_qa", "grammar", "creative_writing", "revision"],
    "Maths":    ["concrete", "pictorial_and_abstract", "word_problems", "revision"],
    "Science":  ["revision"],
    "GK":       ["revision"],
    "Islamiat": ["revision"],
    "SST":      ["revision"],
}
```

These are copied verbatim into CPE `config.py` (D-5). The LLM picks `lp_type` only from the list for
the request's `subject`. Note: Science/GK/Islamiat/SST currently expose only `revision` — for those
subjects every unit's lp_type is `revision` (acceptable for v2; revisit if UG_LP adds skill types).
