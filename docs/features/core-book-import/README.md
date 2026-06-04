# Core Book Import — admin dashboard

Turns the one-shot workstation ETL (`scripts/import_ncp_english_g1.py`) into a
self-service **admin dashboard action**: an admin browses importable books from
taleemabad-core (`fde_staging`), picks one, and Dars imports the whole curriculum
cell for that book — **SLOs → sub-SLOs (LLM breakdown + lp_type) → book + chapters
(prose sliced per chapter) → topics → topic↔sub-SLO + chapter↔SLO mappings** — into
the Dars database, scoped to the book's (curriculum, grade, subject).

The import is long-running (core reads + several LLM calls), so it runs as a
**background job** the dashboard polls: POST kicks it off and returns an
`import_run_id`; a new `import_runs` table tracks status / per-step progress /
row counts / errors; the dashboard polls a status endpoint and shows live progress
then a results summary (D-1). Books are chosen by **browsing core** — grade/subject
are derived from the core row, not entered by hand, dropping the script's hard-coded
G1/Eng assertion (D-2). Topics in this first version stay **1-per-chapter** (the
proven script behaviour); real per-topic breakdown is a logged fast-follow (D-3).

## Documents

1. [00-glossary.md](00-glossary.md) — terms (Core Book, Import Run, Curriculum Cell, …).
2. [01-decision-log.md](01-decision-log.md) — D-1…, rationale + when decided.
3. [02-data-model.md](02-data-model.md) — the new `import_runs` table + the core/Dars
   tables the import reads/writes.
4. [03-reference-etl-script.md](03-reference-etl-script.md) — frozen extract of the
   proven `scripts/import_ncp_english_g1.py` logic the service ports.
5. [04-phase-1-backend.md](04-phase-1-backend.md) — core-book browse, import_runs,
   the import service (ported ETL), background job, status endpoint.
6. [05-phase-2-frontend.md](05-phase-2-frontend.md) — dashboard: book picker → import
   form → progress poller → results card.
7. [ONRAMP.md](ONRAMP.md) — *(after plan approval)* single entry point for a fresh agent.

## Document precedence

```
1. 01-decision-log.md         (D-N references are canonical)
2. 02-data-model.md           (schema is ground truth)
3. 00-glossary.md             (terminology)
4. 03-reference-etl-script.md (frozen source-of-truth for ETL behaviour)
5. phase docs (04, 05)        (specs derived from above)
6. running code               (last; code may be stale)
```
