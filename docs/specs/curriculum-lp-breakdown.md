# Curriculum LP Breakdown

**Date:** 2026-04-14
**Status:** Planned

---

## Goal

Given a book's topics (linked to SLOs), automatically produce a full curriculum plan of LP stubs that UG LP can generate actual lesson plans from.

---

## Data Model

### 1. Sub-SLOs

A breakdown of an SLO into granular learnable parts. Authored manually in the Schema tool and imported into dars. Many-to-many with SLOs.

### 2. Topics

A new layer under chapters. Hierarchy: Books → Chapters → Topics. Books and chapters already exist in dars; topics are not yet built.

### 3. Topic ↔ Sub-SLO Links

Many-to-many. A topic can cover multiple sub-SLOs; a sub-SLO can appear across multiple topics.

### 4. Curriculum

An ordered list of topics for a grade/subject, derived from a book. Sequence matters.

### 5. LP Breakdown Module

An AI step that, given a topic and its linked sub-SLOs, decides:

- How many skill-based LPs are needed to cover the topic
- What skill each LP targets (e.g. CPA phase, Bloom's level)
- The sequence of those LPs

Output: a list of LP stubs — each with topic, sub-SLO(s), skill type, and sequence number — ready to hand to UG LP for generation.

---

## Current State

| Component | Status |
|-----------|--------|
| SLO providers + SLOs (NCP) | Done — imported to DB |
| Books + chapters | Done — synced from taleemabad-core |
| Sub-SLOs | Not built |
| Topics | Not built |
| Topic ↔ Sub-SLO links | Not built |
| Curriculum model | Not built |
| LP Breakdown Module | Not built |

---

## Out of Scope

- Continuity enforcement across LPs (not yet defined)
- SNC/Punjab SLO import (NCP only for now)

---

## Build Order

1. Sub-SLOs — schema + import pipeline from Schema tool
2. Topics — new model under chapters
3. Topic ↔ Sub-SLO links
4. Curriculum — ordered topic list per grade/subject/book
5. LP Breakdown Module — AI step producing LP stubs
6. UG LP integration — hand off LP stubs for generation
