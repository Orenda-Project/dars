import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.database import get_db
from dars.deps import get_admin_client, get_current_client

from .models import (
    Curriculum,
    CurriculumLpStub,
    CurriculumTopic,
    Grade,
    Subject,
    SloProvider,
    SubSlo,
    Slo,
    Topic,
)
from .schemas import (
    CurriculumResponse,
    GradeResponse,
    SubjectResponse,
)

router = APIRouter(tags=["curriculum"])


@router.get("/api/v1/grades", response_model=list[GradeResponse])
async def list_grades(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> list[GradeResponse]:
    result = await db.execute(select(Grade).order_by(Grade.order_index))
    return list(result.scalars().all())


@router.get("/api/v1/subjects", response_model=list[SubjectResponse])
async def list_subjects(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> list[SubjectResponse]:
    result = await db.execute(select(Subject).order_by(Subject.label))
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Books browser endpoint — returns mock data (real data to be seeded later)
# ---------------------------------------------------------------------------

_MOCK_BOOKS = [
    {
        "id": 9999,
        "title": "English Grade 1 (Sample)",
        "grade": 1,
        "subject": "English",
        "chapters": [
            {
                "id": 99991,
                "chapter_number": 1,
                "title": "My Family and Me",
                "topics": [
                    {
                        "id": "11111111-1111-1111-1111-111111111101",
                        "title": "Naming family members",
                        "sequence": 1,
                        "sub_slos": [
                            {
                                "id": "22222222-2222-2222-2222-222222222201",
                                "code": "A1-01.1",
                                "statement": "Student can name immediate family members (mother, father, sister, brother).",
                                "slo_code": "A1-01",
                            }
                        ],
                    },
                    {
                        "id": "11111111-1111-1111-1111-111111111102",
                        "title": "Describing family roles",
                        "sequence": 2,
                        "sub_slos": [
                            {
                                "id": "22222222-2222-2222-2222-222222222202",
                                "code": "A1-01.2",
                                "statement": "Student can describe roles of family members using simple sentences.",
                                "slo_code": "A1-01",
                            }
                        ],
                    },
                ],
            },
            {
                "id": 99992,
                "chapter_number": 2,
                "title": "My School",
                "topics": [
                    {
                        "id": "11111111-1111-1111-1111-111111111103",
                        "title": "Classroom objects",
                        "sequence": 1,
                        "sub_slos": [
                            {
                                "id": "22222222-2222-2222-2222-222222222203",
                                "code": "A1-02.1",
                                "statement": "Student can identify and name common classroom objects.",
                                "slo_code": "A1-02",
                            }
                        ],
                    },
                ],
            },
        ],
    }
]


@router.get("/api/v1/curriculum/books")
async def list_curriculum_books(
    _client: Client = Depends(get_current_client),
) -> list:
    return _MOCK_BOOKS


# ---------------------------------------------------------------------------
# Curriculum list and detail — returns mock data
# ---------------------------------------------------------------------------

_MOCK_CURRICULUM_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

_MOCK_CURRICULUMS = [
    {
        "id": _MOCK_CURRICULUM_ID,
        "name": "Grade 1 English NCP Sample 2025-26",
        "provider": "National Curriculum of Pakistan (NCP)",
        "grade": "Grade 1",
        "subject": "English",
        "academic_year": "2025-2026",
        "is_active": True,
    }
]

_MOCK_CURRICULUM_DETAIL = {
    "id": _MOCK_CURRICULUM_ID,
    "name": "Grade 1 English NCP Sample 2025-26",
    "provider": "National Curriculum of Pakistan (NCP)",
    "grade": "Grade 1",
    "subject": "English",
    "academic_year": "2025-2026",
    "topics": [
        {
            "id": "11111111-1111-1111-1111-111111111101",
            "sequence": 1,
            "title": "Naming family members",
            "lp_stubs": [
                {
                    "id": "33333333-3333-3333-3333-333333333301",
                    "sequence": 1,
                    "skill_type": "reading",
                    "cpa_phase": "concrete",
                    "blooms_level": "remember",
                    "status": "pending",
                },
                {
                    "id": "33333333-3333-3333-3333-333333333302",
                    "sequence": 2,
                    "skill_type": "speaking",
                    "cpa_phase": "pictorial",
                    "blooms_level": "understand",
                    "status": "pending",
                },
            ],
        },
        {
            "id": "11111111-1111-1111-1111-111111111102",
            "sequence": 2,
            "title": "Describing family roles",
            "lp_stubs": [
                {
                    "id": "33333333-3333-3333-3333-333333333303",
                    "sequence": 1,
                    "skill_type": "writing",
                    "cpa_phase": "abstract",
                    "blooms_level": "apply",
                    "status": "pending",
                },
            ],
        },
        {
            "id": "11111111-1111-1111-1111-111111111103",
            "sequence": 3,
            "title": "Classroom objects",
            "lp_stubs": [
                {
                    "id": "33333333-3333-3333-3333-333333333304",
                    "sequence": 1,
                    "skill_type": "listening",
                    "cpa_phase": "concrete",
                    "blooms_level": "remember",
                    "status": "pending",
                },
            ],
        },
    ],
}


@router.get("/api/v1/curriculum/curriculums")
async def list_curriculums_v2(
    _client: Client = Depends(get_current_client),
) -> list:
    return _MOCK_CURRICULUMS


@router.get("/api/v1/curriculum/curriculums/{curriculum_id}")
async def get_curriculum_detail(
    curriculum_id: str,
    _client: Client = Depends(get_current_client),
) -> dict:
    if curriculum_id != _MOCK_CURRICULUM_ID:
        raise HTTPException(status_code=404, detail="Curriculum not found.")
    return _MOCK_CURRICULUM_DETAIL


# ---------------------------------------------------------------------------
# Legacy endpoints (kept for backward compatibility)
# ---------------------------------------------------------------------------

@router.get("/api/v1/curriculums")
async def list_active_curriculums(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_current_client),
) -> list:
    result = await db.execute(
        select(Curriculum).where(Curriculum.is_active == True).order_by(Curriculum.name)  # noqa: E712
    )
    rows = list(result.scalars().all())
    # Return basic shape — grade/subject/provider need joins for full labels
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "academic_year": r.academic_year,
            "is_active": r.is_active,
        }
        for r in rows
    ]


@router.get("/api/admin/curriculums")
async def list_all_curriculums(
    db: AsyncSession = Depends(get_db),
    _client: Client = Depends(get_admin_client),
) -> list:
    result = await db.execute(select(Curriculum).order_by(Curriculum.name))
    rows = list(result.scalars().all())
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "academic_year": r.academic_year,
            "is_active": r.is_active,
        }
        for r in rows
    ]
