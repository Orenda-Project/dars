"""
Core Book Import — admin endpoints (core-book-import F-1.3, F-1.5).

Lets an admin browse importable taleemabad-core books and kick off an import as
a background job tracked by the `import_runs` table (D-1). Admin-gated via
`get_current_admin` (the dashboard's session dep, D-5). Core DB is read-only via
`settings.effective_core_db_url`; if unset, endpoints 503 (D-7). One import at a
time (D-8).
"""
import logging
import uuid
from datetime import datetime

import asyncpg
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel

from dars.config import settings
from dars.v2_api import book_import_service as svc
from dars.v2_api.admin_auth import AdminContext, get_current_admin
from dars.v2_api.deps import _asyncpg_url, get_db_conn

log = logging.getLogger("v2_api.book_import")

router = APIRouter(prefix="/api/v2", tags=["v2-book-import"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CoreBook(BaseModel):
    core_book_id: int
    title: str
    publisher: str | None = None
    edition: str | None = None
    published_year: int | None = None
    total_chapters: int | None = None
    grade: str | None = None
    subject: str | None = None
    status: str
    already_imported: bool


class CoreBookListResponse(BaseModel):
    items: list[CoreBook]


class StartImportRequest(BaseModel):
    core_book_id: int
    curriculum_id: uuid.UUID | None = None


class StartImportResponse(BaseModel):
    import_run_id: uuid.UUID


class ImportRunRead(BaseModel):
    id: uuid.UUID
    core_book_id: int
    curriculum_id: uuid.UUID
    grade_id: uuid.UUID
    subject_id: uuid.UUID
    dars_book_id: uuid.UUID | None
    status: str
    current_step: str | None
    steps: dict
    counts: dict
    warnings: list
    error: str | None
    started_by: str | None
    created_at: datetime
    updated_at: datetime


class ImportRunListResponse(BaseModel):
    items: list[ImportRunRead]


def _require_core_configured() -> str:
    dsn = settings.effective_core_db_url
    if not dsn:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="taleemabad-core DB not configured on this server",
        )
    return dsn


async def _open_core_conn(dsn: str) -> asyncpg.Connection:
    conn = await asyncpg.connect(dsn)
    await conn.execute("SET search_path TO fde_staging, public")
    return conn


# ---------------------------------------------------------------------------
# F-1.3 — browse core books
# ---------------------------------------------------------------------------


@router.get("/admin/core-books", response_model=CoreBookListResponse)
async def list_core_books(
    search: str | None = Query(default=None),
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> CoreBookListResponse:
    log.info("list_core_books start admin=%s search=%r", admin.email, search)
    core_dsn = _require_core_configured()

    # Active Dars curriculum code drives the already-imported UUID check.
    cur_row = await conn.fetchrow(
        "SELECT code FROM curriculums WHERE is_active = TRUE ORDER BY code LIMIT 1"
    )
    active_curr_code = cur_row["code"] if cur_row else None

    core = await _open_core_conn(core_dsn)
    try:
        params: list = []
        where = "b.status = 'OnProd' AND b.is_active AND b.deleted_at IS NULL"
        if search:
            params.append(f"%{search}%")
            where += f" AND b.title ILIKE ${len(params)}"
        rows = await core.fetch(
            f"""
            SELECT b.id, b.title, b.publisher, b.edition, b.published_year,
                   b.total_chapters, b.status,
                   g.short_code AS grade, s.short_code AS subject
            FROM fde_staging.book_library_book b
            LEFT JOIN fde_staging.slo_gradesubject gs ON b.grade_subject_id = gs.id
            LEFT JOIN fde_staging.slo_grade g ON gs.grade_id = g.id
            LEFT JOIN fde_staging.slo_subject s ON gs.subject_id = s.id
            WHERE {where}
            ORDER BY b.title
            """,
            *params,
        )
    finally:
        await core.close()

    items: list[CoreBook] = []
    for r in rows:
        already = False
        if active_curr_code and r["grade"] and r["subject"]:
            grade_digits = "".join(ch for ch in (r["grade"] or "") if ch.isdigit())
            ck = f"{active_curr_code}:{r['grade']}:{r['subject']}"
            book_uuid = svc.seed_uuid(f"book:{ck}:{r['id']}")
            exists = await conn.fetchval("SELECT 1 FROM books WHERE id = $1", book_uuid)
            already = exists is not None
            _ = grade_digits  # grade int parsing happens at import time
        items.append(CoreBook(
            core_book_id=r["id"], title=r["title"], publisher=r["publisher"],
            edition=r["edition"], published_year=r["published_year"],
            total_chapters=r["total_chapters"], grade=r["grade"], subject=r["subject"],
            status=r["status"], already_imported=already,
        ))
    log.info("list_core_books done count=%d", len(items))
    return CoreBookListResponse(items=items)


# ---------------------------------------------------------------------------
# F-1.5 — start import + status
# ---------------------------------------------------------------------------


async def _run_import_task(
    run_id: uuid.UUID, core_book_id: int, curriculum_id: uuid.UUID | None,
    core_dsn: str, dars_dsn: str,
) -> None:
    await svc.run_import(
        run_id=run_id, core_book_id=core_book_id, curriculum_id=curriculum_id,
        core_dsn=core_dsn, dars_dsn=dars_dsn,
    )


@router.post(
    "/admin/book-imports",
    response_model=StartImportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_book_import(
    body: StartImportRequest,
    background: BackgroundTasks,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> StartImportResponse:
    log.info("start_book_import start admin=%s core_book_id=%s", admin.email, body.core_book_id)
    core_dsn = _require_core_configured()

    # One running import at a time (D-8).
    running = await conn.fetchval("SELECT 1 FROM import_runs WHERE status = 'running' LIMIT 1")
    if running is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An import is already running; wait for it to finish",
        )

    # Resolve the cell up front so a bad book/grade/subject fails as 422 (not in the bg task).
    core = await _open_core_conn(core_dsn)
    try:
        try:
            cell = await svc.resolve_cell(
                conn, core, core_book_id=body.core_book_id, curriculum_id=body.curriculum_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    finally:
        await core.close()

    run_id = await conn.fetchval(
        """
        INSERT INTO import_runs
            (core_book_id, curriculum_id, grade_id, subject_id, status, started_by)
        VALUES ($1, $2, $3, $4, 'pending', $5)
        RETURNING id
        """,
        body.core_book_id, cell["curriculum_id"], cell["grade_id"], cell["subject_id"],
        admin.email,
    )

    dars_dsn = _asyncpg_url(settings.database_url)
    background.add_task(
        _run_import_task, run_id, body.core_book_id, body.curriculum_id, core_dsn, dars_dsn,
    )
    log.info("start_book_import scheduled run_id=%s", run_id)
    return StartImportResponse(import_run_id=run_id)


@router.get("/admin/book-imports/{run_id}", response_model=ImportRunRead)
async def get_book_import(
    run_id: uuid.UUID,
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ImportRunRead:
    row = await conn.fetchrow("SELECT * FROM import_runs WHERE id = $1", run_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Import run not found")
    return ImportRunRead(**_row_to_run(row))


@router.get("/admin/book-imports", response_model=ImportRunListResponse)
async def list_book_imports(
    admin: AdminContext = Depends(get_current_admin),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> ImportRunListResponse:
    rows = await conn.fetch(
        "SELECT * FROM import_runs ORDER BY created_at DESC LIMIT 50"
    )
    return ImportRunListResponse(items=[ImportRunRead(**_row_to_run(r)) for r in rows])


def _row_to_run(row: asyncpg.Record) -> dict:
    """asyncpg returns JSONB columns as str — decode steps/counts/warnings."""
    import json
    data = dict(row)
    for k in ("steps", "counts", "warnings"):
        v = data.get(k)
        if isinstance(v, str):
            data[k] = json.loads(v)
    return data
