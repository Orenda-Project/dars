"""
F5.2 — Org admin authentication primitives.

bcrypt for password hashing, an `admin_sessions` table for stateful
session tokens. Cookie/header convention: client sends the session id
verbatim as `X-Admin-Session`. (We don't bother signing it — the id is
already a UUID and we look it up in the DB on every request, so
forging requires guessing a v4 UUID + finding a non-revoked unexpired
row.)
"""
import hmac
import logging
import secrets
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg
import bcrypt
from fastapi import Depends, Header, HTTPException, status

from dars.v2_api.deps import get_db_conn

log = logging.getLogger("v2_api.admin_auth")

SESSION_TTL_HOURS = 24 * 14  # 2 weeks


def hash_password(password: str) -> str:
    """bcrypt with cost factor 12 (per spec)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def hash_api_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def make_api_key(prefix: str = "dk_live_") -> tuple[str, str, str]:
    """Generate (raw_key, sha256_hash, display_prefix)."""
    body = secrets.token_urlsafe(24)
    raw = f"{prefix}{body}"
    return raw, hash_api_key(raw), raw[:12]


@dataclass(frozen=True)
class AdminContext:
    admin_id: UUID
    org_id: UUID
    email: str
    name: str
    session_id: UUID


async def create_session(
    conn: asyncpg.Connection, admin_id: UUID
) -> tuple[UUID, datetime]:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)
    row = await conn.fetchrow(
        """
        INSERT INTO admin_sessions (org_admin_id, expires_at)
        VALUES ($1, $2)
        RETURNING id, expires_at
        """,
        admin_id, expires_at,
    )
    return row["id"], row["expires_at"]


async def revoke_session(conn: asyncpg.Connection, session_id: UUID) -> None:
    await conn.execute(
        """
        UPDATE admin_sessions
        SET revoked_at = now()
        WHERE id = $1 AND revoked_at IS NULL
        """,
        session_id,
    )


async def get_current_admin(
    x_admin_session: str | None = Header(default=None, alias="X-Admin-Session"),
    conn: asyncpg.Connection = Depends(get_db_conn),
) -> AdminContext:
    if not x_admin_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing admin session",
        )
    try:
        session_id = UUID(x_admin_session)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed admin session",
        )

    row = await conn.fetchrow(
        """
        SELECT s.id            AS session_id,
               s.expires_at    AS expires_at,
               s.revoked_at    AS revoked_at,
               oa.id           AS admin_id,
               oa.org_id       AS org_id,
               oa.email        AS email,
               oa.name         AS name
        FROM admin_sessions s
        JOIN org_admins oa ON oa.id = s.org_admin_id
        WHERE s.id = $1
        """,
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    if row["revoked_at"] is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session revoked")
    if row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")

    return AdminContext(
        admin_id=row["admin_id"],
        org_id=row["org_id"],
        email=row["email"],
        name=row["name"],
        session_id=row["session_id"],
    )
