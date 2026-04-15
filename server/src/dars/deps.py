import hmac

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.service import get_client_by_api_key
from dars.config import settings
from dars.database import get_db
from dars.teachers.models import Teacher
from dars.teachers.service import get_client_teacher, get_teacher


async def get_current_client(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
) -> Client:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing API key")
    client = await get_client_by_api_key(db, x_api_key)
    if not client:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    return client


async def get_current_teacher(
    x_teacher_id: str | None = Header(default=None, alias="X-Teacher-ID"),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> Teacher | None:
    """Optional teacher dependency. Returns None if X-Teacher-ID header is absent.
    Raises HTTP 404 if the header is present but the teacher is not found under the current client.
    """
    if x_teacher_id is None:
        return None
    import uuid as _uuid
    try:
        teacher_uuid = _uuid.UUID(x_teacher_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    teacher = await get_teacher(db, client_id=current_client.id, teacher_id=teacher_uuid)
    if teacher is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
    return teacher


async def require_teacher(
    teacher: Teacher | None = Depends(get_current_teacher),
) -> Teacher:
    """Strict teacher dependency. Raises HTTP 422 if X-Teacher-ID header is missing."""
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="X-Teacher-ID header is required",
        )
    return teacher


async def get_effective_teacher(
    x_teacher_id: str | None = Header(default=None, alias="X-Teacher-ID"),
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
) -> Teacher:
    """
    Resolve the active teacher for a request.

    - If X-Teacher-ID header is present, look it up and validate it belongs to the client.
    - Otherwise, fall back to the client's is_client_teacher=True teacher.
    - Raises 404 if the header value does not match a known teacher.
    - Raises 422 if neither the header nor a client teacher is found.
    """
    if x_teacher_id is not None:
        import uuid as _uuid
        try:
            teacher_uuid = _uuid.UUID(x_teacher_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
        teacher = await get_teacher(db, client_id=current_client.id, teacher_id=teacher_uuid)
        if teacher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher not found")
        return teacher

    # Fall back to the client's own teacher
    teacher = await get_client_teacher(db, current_client.id)
    if teacher is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No teacher resolved. Provide X-Teacher-ID header or ensure a client teacher exists.",
        )
    return teacher


async def get_admin_client(
    client: Client = Depends(get_current_client),
) -> Client:
    if not client.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return client


async def require_admin_secret(
    x_admin_secret: str | None = Header(default=None, alias="X-Admin-Secret"),
) -> None:
    if not x_admin_secret or not hmac.compare_digest(x_admin_secret, settings.admin_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
