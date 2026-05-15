"""
Dars v2 read-only API.

Lives alongside legacy routers; eventually replaces them.

Structure:
- deps.py     — API key auth → returns OrgContext
- schemas.py  — Pydantic response models for v2 entities
- service.py  — asyncpg queries (no ORM; v2 tables use UUID PKs that
                 conflict with the legacy Base class)
- router.py   — FastAPI routers, mounted as /api/v2/*

Endpoints in this phase (F1.6):
  GET /api/v2/orgs/me
  GET /api/v2/schools                  ?org_id=
  GET /api/v2/schools/{id}
  GET /api/v2/teachers                 ?school_id=
  GET /api/v2/teachers/{id}
  GET /api/v2/academic-years           ?school_id=
  GET /api/v2/academic-years/{id}
  GET /api/v2/classes                  ?school_id=&academic_year_id=&grade_id=
  GET /api/v2/classes/{id}
  GET /api/v2/csts                     ?school_class_id=&teacher_id=
  GET /api/v2/csts/{id}
"""
