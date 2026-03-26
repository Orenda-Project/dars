# ADR-005: Delegate AI Generation to LP Assistant Microservice

**Status:** Accepted (temporary)
**Date:** 2026-03-26

## Context
Lesson plan generation requires an LLM. Taleemabad already has a working LP Assistant microservice at `lp-assistant.taleemabad.com` that handles prompt engineering, bilingual generation, and model calls.

## Decision
Dars calls the existing LP Assistant microservice for generation and AI edits. Dars does not own LLM logic in this phase.

## Reasons
- Fastest path to a working service — LP Assistant is proven and already running
- Avoids duplicating prompt engineering work
- Separation of concerns: Dars handles orchestration and storage; LP Assistant handles AI

## Consequences
- Dars has a runtime dependency on LP Assistant — if it's down, generation fails
- LP Assistant API contract must not break without coordinating with Dars
- Internalize LP logic into Dars in a future phase when the service matures
