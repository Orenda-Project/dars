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
