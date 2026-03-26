# Dars Plan A: Repo Bootstrap + FastAPI Skeleton + Supabase Schema + Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running FastAPI service connected to Supabase with API key auth, client management, and a health endpoint — ready for lesson plan logic in Plan B.

**Architecture:** FastAPI app with async SQLAlchemy connected to Supabase PostgreSQL. Clients (B2B tenants) authenticate via `X-API-Key` header. Raw API keys are hashed (SHA-256) before storage — shown once on creation. All data tables carry a `client_id` FK for row-level isolation. No Celery — FastAPI BackgroundTasks for async work.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x async, asyncpg, pydantic-settings, Supabase PostgreSQL, pytest + pytest-asyncio + httpx, Docker, uv (package manager)

---

## File Map

```
dars/
├── .env                          # git-ignored — real creds
├── .env.example                  # committed — blank template
├── .gitignore
├── CLAUDE.md                     # project memory
├── README.md
├── docker-compose.yml
│
├── supabase/
│   ├── config.toml
│   └── migrations/
│       └── 20260326000001_init.sql
│
└── api/
    ├── Dockerfile
    ├── pyproject.toml
    └── src/
        └── dars/
            ├── main.py           # FastAPI app factory + router registration
            ├── config.py         # pydantic-settings Settings class
            ├── database.py       # async engine + session factory
            ├── deps.py           # FastAPI dependencies: get_db, get_client
            ├── clients/
            │   ├── models.py     # Client SQLAlchemy model
            │   ├── schemas.py    # Pydantic request/response schemas
            │   ├── service.py    # create_client, get_client_by_key_hash
            │   └── router.py     # POST /internal/clients
            └── tests/
                ├── conftest.py   # pytest fixtures: async engine, test db, test client
                ├── test_health.py
                └── test_clients.py
```

---

## Task 1: Repo scaffolding + git init

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `CLAUDE.md`

- [ ] **Step 1: Initialize git repo**

```bash
cd /home/hataf/taleemabad/dars
git init
```

Expected: `Initialized empty Git repository in .../dars/.git/`

- [ ] **Step 2: Create .gitignore**

Create `/home/hataf/taleemabad/dars/.gitignore`:

```gitignore
# Environment
.env
*.env.local

# Python
__pycache__/
*.pyc
*.pyo
.venv/
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/
.ruff_cache/
htmlcov/
.coverage

# Node
node_modules/
packages/*/dist/
packages/*/.turbo/
*.tsbuildinfo

# Supabase
supabase/.temp/

# OS
.DS_Store
*.swp
```

- [ ] **Step 3: Create .env.example**

Create `/home/hataf/taleemabad/dars/.env.example`:

```bash
# Copy this file to .env and fill in your values
# Never commit .env to git

# Supabase
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=

# Database — get the "Transaction" connection string from Supabase dashboard > Settings > Database
# Replace [YOUR-PASSWORD] with your database password
DATABASE_URL=postgresql+asyncpg://postgres.[project-ref]:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres

# LP Assistant microservice
LP_ASSISTANT_URL=https://lp-assistant.taleemabad.com
LP_ASSISTANT_API_KEY=

# App settings
DEBUG=false
INTERNAL_API_SECRET=change-me-to-a-random-string
```

- [ ] **Step 4: Create README.md**

Create `/home/hataf/taleemabad/dars/README.md`:

```markdown
# Dars (درس)

B2B lesson plan infrastructure for Taleemabad internal teams.

## What this is

Dars exposes lesson plan creation and rendering as a service. Teams building apps for specific regions can integrate LP functionality by:

1. Installing `@dars/client` or `@dars/react` from npm
2. Pointing it at the Dars API with their API key

## Repo structure

```
api/          FastAPI backend service
packages/
  dars-client/   TypeScript API client (@dars/client)
  dars-react/    React components (@dars/react)
supabase/     Database migrations (Supabase CLI)
docs/         Design specs, ADRs, API reference
```

## Local dev setup

### Prerequisites
- Python 3.12+
- uv (`pip install uv`)
- Supabase CLI (`brew install supabase/tap/supabase` or see supabase.com/docs/guides/cli)
- Docker (for running the API in a container)

### 1. Configure credentials

```bash
cp .env.example .env
# Fill in .env with your Supabase credentials and LP Assistant key
```

### 2. Apply database migrations

```bash
supabase link --project-ref <your-project-ref>
supabase db push
```

### 3. Run the API

```bash
cd api
uv sync
uv run uvicorn dars.main:app --reload
```

API available at http://localhost:8000
Swagger docs at http://localhost:8000/docs

### 4. Run tests

```bash
cd api
uv run pytest
```

## Creating a B2B client

```bash
curl -X POST http://localhost:8000/internal/clients \
  -H "X-Internal-Secret: <INTERNAL_API_SECRET from .env>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Punjab Team"}'
```

Returns an API key — store it safely, it is shown only once.
```

- [ ] **Step 5: Create CLAUDE.md**

Create `/home/hataf/taleemabad/dars/CLAUDE.md`:

```markdown
# Dars — Project Memory

## What this is
Dars (درس, "lesson") is a standalone B2B service that provides lesson plan (LP) creation and rendering infrastructure for Taleemabad internal teams. It is NOT a monolith — it is a focused service with a documented API and reusable npm packages.

## Repo layout
- `api/` — FastAPI backend (Python 3.12, SQLAlchemy async, asyncpg)
- `packages/dars-client/` — TypeScript API client (`@dars/client`)
- `packages/dars-react/` — React components (`@dars/react`)
- `supabase/` — Database migrations managed by Supabase CLI
- `docs/superpowers/specs/` — Design specs
- `docs/superpowers/plans/` — Implementation plans
- `docs/adr/` — Architecture Decision Records

## Key decisions
- **FastAPI** over Django REST — async-native, auto OpenAPI, lighter
- **Supabase** (hosted Postgres) — no local DB container, dashboard for inspection
- **Row-level isolation** — `client_id` FK on all data tables, no schema-per-tenant
- **API keys** — SHA-256 hashed, shown once on creation, never stored plain
- **BackgroundTasks** — no Celery; FastAPI built-in is sufficient for now
- **LP Assistant** — AI generation delegated to `lp-assistant.taleemabad.com` for now

## Commands
```bash
# Run API (dev)
cd api && uv run uvicorn dars.main:app --reload

# Run tests
cd api && uv run pytest

# Apply DB migrations
supabase db push

# Build client package
cd packages/dars-client && pnpm build

# Build react package
cd packages/dars-react && pnpm build
```

## Conventions
- All DB models in `models.py`, Pydantic schemas in `schemas.py`, business logic in `service.py`
- Every public endpoint requires `X-API-Key` header — enforced in `deps.py:get_current_client`
- Internal endpoints (client management) require `X-Internal-Secret` header
- All DB queries must filter by `client_id` — never query without it on data tables
- UUIDs everywhere for IDs
- Migrations go in `supabase/migrations/` as plain SQL files named `YYYYMMDDHHMMSS_description.sql`
- Tests use an in-memory SQLite via `aiosqlite` — no real Supabase connection needed for tests
```

- [ ] **Step 6: Initial commit**

```bash
cd /home/hataf/taleemabad/dars
git add .gitignore .env.example README.md CLAUDE.md
git commit -m "chore: initialize Dars repo with project scaffolding"
```

---

## Task 2: FastAPI project setup with uv

**Files:**
- Create: `api/pyproject.toml`
- Create: `api/src/dars/__init__.py`
- Create: `api/src/dars/main.py`
- Create: `api/src/dars/config.py`

- [ ] **Step 1: Create pyproject.toml**

Create `/home/hataf/taleemabad/dars/api/pyproject.toml`:

```toml
[project]
name = "dars-api"
version = "0.1.0"
description = "Dars lesson plan service API"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "aiosqlite>=0.20.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.uv]
package = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/dars"]
```

- [ ] **Step 2: Install dependencies**

```bash
cd /home/hataf/taleemabad/dars/api
uv sync --extra dev
```

Expected: resolves and installs all packages into `.venv/`

- [ ] **Step 3: Create config.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str = "sqlite+aiosqlite:///./test.db"
    debug: bool = False
    internal_api_secret: str = "dev-secret"
    lp_assistant_url: str = "https://lp-assistant.taleemabad.com"
    lp_assistant_api_key: str = ""


settings = Settings()
```

- [ ] **Step 4: Create main.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/main.py`:

```python
from fastapi import FastAPI

from dars.config import settings

app = FastAPI(
    title="Dars API",
    description="Lesson plan infrastructure for Taleemabad internal teams",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
```

- [ ] **Step 5: Create `__init__.py`**

Create `/home/hataf/taleemabad/dars/api/src/dars/__init__.py`:

```python
```

(empty file)

- [ ] **Step 6: Verify API starts**

```bash
cd /home/hataf/taleemabad/dars/api
uv run uvicorn dars.main:app --reload --port 8000
```

Expected: `Uvicorn running on http://127.0.0.1:8000`. Hit Ctrl+C to stop.

- [ ] **Step 7: Write failing health test**

Create `/home/hataf/taleemabad/dars/api/tests/__init__.py` (empty).

Create `/home/hataf/taleemabad/dars/api/tests/conftest.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport

from dars.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

Create `/home/hataf/taleemabad/dars/api/tests/test_health.py`:

```python
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

- [ ] **Step 8: Run test — expect pass**

```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/test_health.py -v
```

Expected:
```
PASSED tests/test_health.py::test_health
```

- [ ] **Step 9: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add api/
git commit -m "feat: FastAPI skeleton with health endpoint and config"
```

---

## Task 3: Database setup (SQLAlchemy async)

**Files:**
- Create: `api/src/dars/database.py`

- [ ] **Step 1: Write failing test for DB session**

Create `/home/hataf/taleemabad/dars/api/tests/test_database.py`:

```python
from sqlalchemy.ext.asyncio import AsyncSession
from dars.database import get_db, engine, Base


async def test_db_session_yields_async_session():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    gen = get_db()
    session = await gen.__anext__()
    assert isinstance(session, AsyncSession)
    await gen.aclose()
```

Run it:
```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/test_database.py -v
```
Expected: FAIL with `ImportError: cannot import name 'get_db'`

- [ ] **Step 2: Create database.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/database.py`:

```python
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from dars.config import settings


engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: Run test — expect pass**

```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/test_database.py -v
```

Expected: `PASSED`

- [ ] **Step 4: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add api/src/dars/database.py api/tests/test_database.py
git commit -m "feat: async SQLAlchemy engine and session factory"
```

---

## Task 4: Client model + service

**Files:**
- Create: `api/src/dars/clients/models.py`
- Create: `api/src/dars/clients/schemas.py`
- Create: `api/src/dars/clients/service.py`
- Create: `api/src/dars/clients/__init__.py`

- [ ] **Step 1: Write failing tests**

Create `/home/hataf/taleemabad/dars/api/tests/test_clients.py`:

```python
import hashlib
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dars.database import Base
from dars.clients.models import Client
from dars.clients.service import create_client, get_client_by_api_key


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def test_create_client_returns_name_and_key(db):
    client, raw_key = await create_client(db, name="Punjab Team")
    assert client.name == "Punjab Team"
    assert client.is_active is True
    assert len(raw_key) > 20
    assert raw_key.startswith("dars_")


async def test_create_client_stores_hash_not_plaintext(db):
    client, raw_key = await create_client(db, name="Sindh Team")
    expected_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    assert client.api_key_hash == expected_hash
    assert raw_key not in client.api_key_hash


async def test_get_client_by_api_key_found(db):
    client, raw_key = await create_client(db, name="Test Team")
    found = await get_client_by_api_key(db, raw_key)
    assert found is not None
    assert found.id == client.id


async def test_get_client_by_api_key_not_found(db):
    found = await get_client_by_api_key(db, "dars_invalid_key")
    assert found is None


async def test_get_client_by_api_key_inactive(db):
    client, raw_key = await create_client(db, name="Disabled Team")
    client.is_active = False
    await db.commit()
    found = await get_client_by_api_key(db, raw_key)
    assert found is None
```

Run:
```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/test_clients.py -v
```
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 2: Create clients/__init__.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/clients/__init__.py` (empty).

- [ ] **Step 3: Create clients/models.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/clients/models.py`:

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from dars.database import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
```

- [ ] **Step 4: Create clients/service.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/clients/service.py`:

```python
import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _generate_api_key() -> str:
    return f"dars_{secrets.token_urlsafe(32)}"


async def create_client(db: AsyncSession, name: str) -> tuple[Client, str]:
    """Create a new client. Returns (client, raw_api_key). Raw key shown once — not stored."""
    raw_key = _generate_api_key()
    client = Client(
        id=uuid.uuid4(),
        name=name,
        api_key_hash=_hash_key(raw_key),
    )
    db.add(client)
    await db.commit()
    await db.refresh(client)
    return client, raw_key


async def get_client_by_api_key(db: AsyncSession, raw_key: str) -> Client | None:
    """Look up active client by raw API key. Returns None if not found or inactive."""
    key_hash = _hash_key(raw_key)
    result = await db.execute(
        select(Client).where(
            Client.api_key_hash == key_hash,
            Client.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()
```

- [ ] **Step 5: Run tests — expect pass**

```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/test_clients.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 6: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add api/src/dars/clients/ api/tests/test_clients.py
git commit -m "feat: Client model and API key service (hash-only storage)"
```

---

## Task 5: Auth dependency + internal client creation endpoint

**Files:**
- Create: `api/src/dars/deps.py`
- Create: `api/src/dars/clients/schemas.py`
- Create: `api/src/dars/clients/router.py`
- Modify: `api/src/dars/main.py`

- [ ] **Step 1: Write failing tests**

Add to `/home/hataf/taleemabad/dars/api/tests/test_clients.py`:

```python
# --- Router tests ---
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
from dars.main import app
from dars.clients.models import Client
import uuid
from datetime import datetime, timezone


@pytest.fixture
def mock_client_obj():
    return Client(
        id=uuid.uuid4(),
        name="Test Team",
        api_key_hash="abc123",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


@pytest.fixture
async def http_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_create_client_endpoint_requires_internal_secret(http_client):
    response = await http_client.post(
        "/internal/clients",
        json={"name": "Punjab Team"},
    )
    assert response.status_code == 403


async def test_create_client_endpoint_success(http_client, mock_client_obj):
    with patch("dars.clients.router.create_client", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = (mock_client_obj, "dars_fake_raw_key")
        response = await http_client.post(
            "/internal/clients",
            headers={"X-Internal-Secret": "dev-secret"},
            json={"name": "Punjab Team"},
        )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Team"
    assert data["api_key"] == "dars_fake_raw_key"
    assert "api_key_hash" not in data


async def test_api_key_auth_missing(http_client):
    response = await http_client.get("/api/v1/me")
    assert response.status_code == 401


async def test_api_key_auth_invalid(http_client):
    response = await http_client.get(
        "/api/v1/me",
        headers={"X-API-Key": "dars_invalid"},
    )
    assert response.status_code == 401


async def test_api_key_auth_valid(http_client, mock_client_obj):
    with patch("dars.deps.get_client_by_api_key", new_callable=AsyncMock) as mock_lookup:
        mock_lookup.return_value = mock_client_obj
        response = await http_client.get(
            "/api/v1/me",
            headers={"X-API-Key": "dars_valid_key"},
        )
    assert response.status_code == 200
    assert response.json()["name"] == "Test Team"
```

Run:
```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/test_clients.py -v -k "endpoint or auth"
```
Expected: FAIL (routes don't exist yet)

- [ ] **Step 2: Create clients/schemas.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/clients/schemas.py`:

```python
import uuid
from datetime import datetime

from pydantic import BaseModel


class ClientCreateRequest(BaseModel):
    name: str


class ClientCreateResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime
    api_key: str  # raw key — shown once only

    model_config = {"from_attributes": True}


class ClientPublicResponse(BaseModel):
    id: uuid.UUID
    name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Create deps.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/deps.py`:

```python
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.service import get_client_by_api_key
from dars.config import settings
from dars.database import get_db


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


async def require_internal_secret(
    x_internal_secret: str | None = Header(default=None, alias="X-Internal-Secret"),
) -> None:
    if x_internal_secret != settings.internal_api_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
```

- [ ] **Step 4: Create clients/router.py**

Create `/home/hataf/taleemabad/dars/api/src/dars/clients/router.py`:

```python
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from dars.clients.models import Client
from dars.clients.schemas import ClientCreateRequest, ClientCreateResponse, ClientPublicResponse
from dars.clients.service import create_client
from dars.database import get_db
from dars.deps import get_current_client, require_internal_secret

internal_router = APIRouter(prefix="/internal", tags=["internal"])
client_router = APIRouter(prefix="/api/v1", tags=["clients"])


@internal_router.post(
    "/clients",
    status_code=status.HTTP_201_CREATED,
    response_model=ClientCreateResponse,
    dependencies=[Depends(require_internal_secret)],
)
async def create_client_endpoint(
    body: ClientCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> ClientCreateResponse:
    client, raw_key = await create_client(db, name=body.name)
    return ClientCreateResponse(
        id=client.id,
        name=client.name,
        is_active=client.is_active,
        created_at=client.created_at,
        api_key=raw_key,
    )


@client_router.get("/me", response_model=ClientPublicResponse)
async def get_me(current_client: Client = Depends(get_current_client)) -> ClientPublicResponse:
    return ClientPublicResponse.model_validate(current_client)
```

- [ ] **Step 5: Update main.py to register routers**

Replace `/home/hataf/taleemabad/dars/api/src/dars/main.py` with:

```python
from fastapi import FastAPI

from dars.clients.router import client_router, internal_router
from dars.config import settings

app = FastAPI(
    title="Dars API",
    description="Lesson plan infrastructure for Taleemabad internal teams",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(internal_router)
app.include_router(client_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "debug": settings.debug}
```

- [ ] **Step 6: Run all tests — expect pass**

```bash
cd /home/hataf/taleemabad/dars/api
uv run pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add api/src/dars/deps.py api/src/dars/clients/ api/src/dars/main.py api/tests/
git commit -m "feat: API key auth dependency and internal client creation endpoint"
```

---

## Task 6: Supabase migrations

**Files:**
- Create: `supabase/config.toml`
- Create: `supabase/migrations/20260326000001_init.sql`

- [ ] **Step 1: Create supabase/config.toml**

Create `/home/hataf/taleemabad/dars/supabase/config.toml`:

```toml
project_id = "dars"

[api]
enabled = true
port = 54321
schemas = ["public"]

[db]
port = 54322

[studio]
enabled = true
port = 54323
```

- [ ] **Step 2: Create initial migration SQL**

Create `/home/hataf/taleemabad/dars/supabase/migrations/20260326000001_init.sql`:

```sql
-- Enable UUID generation
create extension if not exists "pgcrypto";

-- Clients table (B2B tenants)
create table if not exists clients (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    api_key_hash text not null unique,
    is_active boolean not null default true,
    created_at timestamptz not null default now()
);

-- Lesson plans table
create table if not exists lesson_plans (
    id uuid primary key default gen_random_uuid(),
    client_id uuid not null references clients(id) on delete cascade,
    external_ref text,
    grade text not null,
    subject text not null,
    topic text,
    page_number integer,
    class_strength integer,
    content text,
    content_bilingual text,
    status text not null default 'PENDING' check (status in ('PENDING', 'READY', 'ERROR')),
    metadata jsonb not null default '{}',
    tags jsonb not null default '{}',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists lesson_plans_client_id_idx on lesson_plans(client_id);
create index if not exists lesson_plans_status_idx on lesson_plans(status);
create index if not exists lesson_plans_created_at_idx on lesson_plans(created_at desc);

-- Lesson plan edits table
create table if not exists lesson_plan_edits (
    id uuid primary key default gen_random_uuid(),
    lesson_plan_id uuid not null references lesson_plans(id) on delete cascade,
    content text not null,
    edit_source text not null check (edit_source in ('USER', 'AI', 'GENERATED')),
    edit_instruction text,
    metadata jsonb not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists lesson_plan_edits_lp_id_idx on lesson_plan_edits(lesson_plan_id);

-- Auto-update updated_at on lesson_plans
create or replace function update_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

create trigger lesson_plans_updated_at
    before update on lesson_plans
    for each row execute function update_updated_at();
```

- [ ] **Step 3: Document how to apply to Supabase**

This step is instructions only — no code to run yet (requires a real Supabase project).

To apply migrations to your Supabase project:
```bash
# One-time: link your local project to your Supabase project
supabase link --project-ref <your-project-ref>

# Apply migrations
supabase db push
```

Get `<your-project-ref>` from your Supabase dashboard URL: `https://app.supabase.com/project/<ref>`

- [ ] **Step 4: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add supabase/
git commit -m "feat: Supabase migration for clients, lesson_plans, lesson_plan_edits tables"
```

---

## Task 7: Docker setup

**Files:**
- Create: `api/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: Create Dockerfile**

Create `/home/hataf/taleemabad/dars/api/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv sync --no-dev

# Run the app
CMD ["uv", "run", "uvicorn", "dars.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create docker-compose.yml**

Create `/home/hataf/taleemabad/dars/docker-compose.yml`:

```yaml
services:
  api:
    build:
      context: ./api
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - DEBUG=true
    volumes:
      - ./api/src:/app/src  # hot reload in dev
    command: uv run uvicorn dars.main:app --host 0.0.0.0 --port 8000 --reload
```

Note: No database service here — Supabase is hosted. Just the API container.

- [ ] **Step 3: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add api/Dockerfile docker-compose.yml
git commit -m "chore: Docker setup for API container"
```

---

## Task 8: ADR documents

**Files:**
- Create: `docs/adr/001-fastapi-over-django.md`
- Create: `docs/adr/002-row-level-multitenancy.md`
- Create: `docs/adr/003-supabase-database.md`
- Create: `docs/adr/004-api-keys-over-jwt.md`
- Create: `docs/adr/005-delegate-lp-assistant.md`

- [ ] **Step 1: Create ADR-001**

Create `/home/hataf/taleemabad/dars/docs/adr/001-fastapi-over-django.md`:

```markdown
# ADR-001: FastAPI over Django REST Framework

**Status:** Accepted
**Date:** 2026-03-26

## Context
Dars is an independent service, not a monolith feature. The existing taleemabad-core uses Django REST Framework. We need to choose a Python web framework for Dars.

## Decision
Use FastAPI.

## Reasons
- Async-native: lesson plan generation involves waiting on an external AI service; async handles this without thread pool overhead
- Auto-generates OpenAPI/Swagger from code — documentation is a first-class concern for a B2B SDK service
- Lighter than Django: no ORM coupling, no admin, no templating — we only need an API
- pydantic-settings gives clean 12-factor config
- Easier to write and test async code than Django's sync-by-default model

## Consequences
- Team must learn FastAPI patterns (dependency injection, lifespan events) instead of Django patterns
- SQLAlchemy replaces Django ORM — more verbose but more explicit
- No Django admin — internal client management done via API endpoint
```

- [ ] **Step 2: Create ADR-002**

Create `/home/hataf/taleemabad/dars/docs/adr/002-row-level-multitenancy.md`:

```markdown
# ADR-002: Row-Level Multi-Tenancy

**Status:** Accepted
**Date:** 2026-03-26

## Context
Multiple internal teams (Punjab, Sindh, etc.) will use Dars. Their data must be isolated — one team cannot see another's lesson plans.

## Decision
Use row-level isolation: every data table has a `client_id` UUID foreign key. All queries filter by `client_id`. Single schema, single database.

## Reasons
- Simpler than schema-per-tenant (no per-tenant migrations, no connection switching)
- Sufficient for internal B2B — teams are Taleemabad employees, not untrusted external customers
- PostgreSQL RLS (Row Level Security) can be added later as an extra safety layer
- Easier to query across clients for analytics if ever needed

## Consequences
- Developers must remember to always filter by `client_id` — enforced via the `get_current_client` dependency
- A bug that forgets `client_id` could expose cross-tenant data — mitigated by code review and tests
```

- [ ] **Step 3: Create ADR-003**

Create `/home/hataf/taleemabad/dars/docs/adr/003-supabase-database.md`:

```markdown
# ADR-003: Supabase for Database Hosting

**Status:** Accepted
**Date:** 2026-03-26

## Context
We need a PostgreSQL database. Options: self-hosted Docker, managed RDS, or Supabase.

## Decision
Use Supabase hosted PostgreSQL.

## Reasons
- No local database container needed — developers just copy `.env.example` and fill in credentials
- Supabase dashboard provides a table viewer and SQL editor for quick inspection
- Free tier is sufficient for early development
- Supabase CLI allows migrations to be managed in code (`supabase/migrations/`)
- Standard PostgreSQL under the hood — can migrate away if needed

## Consequences
- Developers need a Supabase project (created once manually in the dashboard)
- Supabase project ref and DB password must be shared with team via secure channel
- Internet required for local dev (no offline DB option without Docker)
```

- [ ] **Step 4: Create ADR-004**

Create `/home/hataf/taleemabad/dars/docs/adr/004-api-keys-over-jwt.md`:

```markdown
# ADR-004: API Keys Over JWT for B2B Auth

**Status:** Accepted
**Date:** 2026-03-26

## Context
B2B clients (internal teams) need to authenticate with the Dars API. Options: API keys, JWT, OAuth2.

## Decision
API keys with SHA-256 hashing. Each client gets one key on creation.

## Reasons
- Stateless: no token refresh, no OAuth flows
- Simple: client sets `X-API-Key` header on every request — no token management library needed
- Sufficient: clients are internal teams, not end-users with individual identities
- SHA-256 hashing: raw key never stored, only the hash — a DB breach doesn't expose keys

## Consequences
- No per-user identity within a client — all requests from a client team look the same
- Key rotation requires creating a new client or implementing a key rotation endpoint (future)
- If per-teacher identity is needed later, JWT can be layered on top
```

- [ ] **Step 5: Create ADR-005**

Create `/home/hataf/taleemabad/dars/docs/adr/005-delegate-lp-assistant.md`:

```markdown
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
```

- [ ] **Step 6: Commit**

```bash
cd /home/hataf/taleemabad/dars
git add docs/adr/
git commit -m "docs: add Architecture Decision Records 001-005"
```

---

## Verification Checklist

After completing all tasks, verify the following:

- [ ] `cd api && uv run pytest` — all tests pass
- [ ] `uv run uvicorn dars.main:app --reload` — server starts, `GET /health` returns `{"status": "ok"}`
- [ ] `GET /docs` in browser — Swagger UI shows `/health`, `/internal/clients`, `/api/v1/me`
- [ ] `POST /internal/clients` without secret → 403
- [ ] `POST /internal/clients` with `X-Internal-Secret: dev-secret` → 201 with `api_key` field
- [ ] `GET /api/v1/me` without key → 401
- [ ] `GET /api/v1/me` with invalid key → 401
- [ ] `git log --oneline` — 8 clean commits
- [ ] `cat .gitignore` — `.env` is listed
- [ ] `supabase/migrations/20260326000001_init.sql` exists with correct SQL
