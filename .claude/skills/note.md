---
name: note
description: Add a personal note to docs/personal/. Routes to the right file based on content type.
user-invocable: true
---

Append or create a note in `docs/personal/` based on these rules:

## Routing rules

1. **One-liner or loose thought** — append to `docs/personal/notes.md` under a relevant existing section, or add a new `## Section` if nothing fits.

2. **A decision with reasoning** — create or append to a doc named after the topic (e.g. `docs/personal/auth_decision.md`). Format:
   - What was decided
   - Why
   - What to avoid / watch out for

3. **A named topic with multiple points** — create a new doc named after the topic (e.g. `docs/personal/roadmap_domains.md`). Use the topic as the `# Title`.

4. **Addition to an existing personal doc** — if a relevant doc already exists in `docs/personal/`, append to it instead of creating a new one. Always check first.

## Rules

- Never modify any doc outside `docs/personal/`
- Always start by listing `docs/personal/` to see what already exists
- Add the date (`YYYY-MM-DD`) to decisions and named topic docs, not to loose notes
- Keep it terse — personal notes are for future-you, not for documentation
- Do not add a preamble or confirmation message, just write the note and say where you put it in one line
