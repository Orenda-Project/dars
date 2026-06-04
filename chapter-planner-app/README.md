# Chapter Planning Engine (CPE)

Standalone FastAPI service that decides **which lesson plans to generate for a chapter**.
Given a chapter (topics + SLOs), a subject, a grade, and a period count, it produces that
many ordered Plan Units — each picking an `lp_type`, grouping topics, and listing the SLOs
it covers — so each unit maps losslessly onto UG_LessonPlan's `/generate-lp` input. It is
independent of the dars backend (own `main.py`, own process). Phase 1 ships the contract and
a deterministic stub planner; Phase 2 swaps in an LLM planner.

## Quick start

```bash
cd chapter-planner-app
pip install -r requirements.txt          # claude-agent-sdk is unused in Phase 1
cp .env.example .env
uvicorn main:app --port 4100
```

Open <http://localhost:4100/> for the playground.

## Health check

```bash
curl http://localhost:4100/health
# {"status":"ok"}
```

## Plan a chapter

```bash
curl -X POST http://localhost:4100/plan \
  -H 'Content-Type: application/json' \
  -d '{"subject":"Eng","grade":1,"curriculum":"ICT","period_count":3,
       "chapter":{"title":"Chapter 1 — Myself","topics":[
         {"id":"t1","topic_text":"Greetings","slos":[{"id":"s1","statement":"Student can greet others"}]}]}}'
```

Returns a `ChapterPlan` with `period_count` units (Phase 1: deterministic stub).
