# Dars (درس)

B2B lesson plan infrastructure for Taleemabad internal teams.

## What this is

Dars exposes lesson plan creation and rendering as a service. Teams building apps for specific regions can integrate LP functionality by:

1. Installing `@dars/client` or `@dars/react` from npm
2. Pointing it at the Dars API with their API key

## Repo structure

```
server/          FastAPI backend service
packages/
  dars-client/   TypeScript API client (@dars/client)
  dars-react/    React components (@dars/react)
supabase/     Database migrations (Supabase CLI)
bruno/        API request collection (Bruno)
docs/
  superpowers/specs/   Design specs
  superpowers/plans/   Implementation plans
  adr/                 Architecture Decision Records
```

## Local dev setup

### Prerequisites
- Python 3.12+
- uv (install via `curl -LsSf https://astral.sh/uv/install.sh | sh` or `pip install uv`)
- Supabase CLI (`brew install supabase/tap/supabase` or see supabase.com/docs/guides/cli)

### 1. Configure credentials

```bash
cp .env.example .env
# Fill in .env with your Supabase credentials and LP Assistant key
```

### 2. Link and apply database migrations

Add your Supabase project ref to `.env` (`DB_DEV_REF=...`), then:

```bash
make db-link   # link CLI to the dev project (one-time per machine)
make db-push   # apply migrations
```

### 3. Install Python dependencies

```bash
cd api && uv sync --extra dev
```

### 4. Run the API

```bash
make dev
```

API available at http://localhost:8000
Swagger docs at http://localhost:8000/docs

### 5. Run tests

```bash
make test
```

### 6. Build frontend packages (optional)

Requires Node.js 18+ and pnpm (`npm install -g pnpm`).

```bash
# Build TypeScript API client
cd packages/dars-client && pnpm install && pnpm build

# Build React components
cd packages/dars-react && pnpm install && pnpm build
```

## Testing the API (Bruno)

API requests are defined in `bruno/` and can be run from VS Code using the [Bruno extension](https://marketplace.visualstudio.com/items?itemName=bruno-api-client.bruno).

**Setup:**
1. Install the Bruno VS Code extension
2. Open `bruno/` as the collection in Bruno
3. Select the `dev` environment
4. Fill in your secrets in the environment — `adminSecret` (from `.env`) and `apiKey` (from creating a client)

**Environments:** Bruno separates vars by environment (`dev`, `prod`, etc.). The `dev` environment is gitignored since it contains secrets — each developer fills in their own. `baseUrl` defaults to `http://localhost:8000`.

**Available requests:**
- `health` — health check
- `admin/create-client` — provision a new B2B client (requires `adminSecret`)
- `lesson-plans/create` — generate a lesson plan
- `lesson-plans/list` — list lesson plans
- `lesson-plans/get` — get a single lesson plan by ID
- `lesson-plans/me` — get current client info

## Creating a B2B client

Use the `admin/create-client` request in Bruno, or via curl:

```bash
curl -X POST http://localhost:8000/admin/clients \
  -H "X-Admin-Secret: <ADMIN_SECRET from .env>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Punjab Team"}'
```

Returns an API key — store it safely, it is shown only once.
