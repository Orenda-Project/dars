from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from dars.auth.schemas import AuthResponse, LoginRequest, SignupRequest
from dars.auth.service import login, signup
from dars.database import get_db

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup_endpoint(
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Register a new client account.

    Returns the API key once — store it securely. It cannot be recovered;
    use POST /auth/login to rotate and retrieve a fresh key.
    """
    client, raw_key = await signup(db, body.email, body.password, body.name)
    return AuthResponse(
        api_key=raw_key,
        client_id=str(client.id),
        name=client.name,
        email=client.email,  # type: ignore[arg-type]
    )


@auth_router.post("/login", response_model=AuthResponse)
async def login_endpoint(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """
    Authenticate and receive a rotated API key.

    Every successful login issues a **new** API key and invalidates the previous one.
    Update your stored key after each call.
    """
    client, raw_key = await login(db, body.email, body.password)
    return AuthResponse(
        api_key=raw_key,
        client_id=str(client.id),
        name=client.name,
        email=client.email,  # type: ignore[arg-type]
    )
