# Features

One folder per feature under `docs/features/<slug>/`. Each folder has its own `README.md`, `ONRAMP.md` (after plan approval), `01-decision-log.md`, and one or more phase docs. See `dars/.claude/skills/feature/SKILL.md` for the workflow.

The v2 rebuild (`docs/plans/2026-05-15-dars-v2-rebuild/`) predates this convention and stays where it is; new features start here.

## Active

_(none)_

## Closed

- [breakdown-slot-editing](breakdown-slot-editing/README.md) — org-admin per-slot editing (slot_type / lp_type / topic_id) + add/delete in draft org breakdowns. Shipped 2026-05-20 via PR #84.
- [lp-slo-injection-and-linkage](lp-slo-injection-and-linkage/README.md) — inject topic sub-SLOs into LP Assistant `custom_prompt` and persist the requested set on `generated_lps`. Shipped 2026-05-20 via PR #82.
