-include .env
export

.PHONY: dev test db-migrate db-new bruno-sync webapp up

dev:
	cd server && uv run uvicorn dars.main:app --reload

test:
	cd server && uv run pytest

db-migrate:
	cd server && uv run python -c "import asyncio; from dars.migrations import run_migrations; from dars.config import settings; asyncio.run(run_migrations(settings.database_url))"

db-new:
	@read -p "Migration name: " name; \
	ts=$$(date +%Y%m%d%H%M%S); \
	touch server/src/dars/migrations/$${ts}_$${name}.sql; \
	echo "Created: server/src/dars/migrations/$${ts}_$${name}.sql"

bruno-sync:
	cd server && uv run python ../scripts/sync_bruno.py

webapp:
	cd webapp && npm run dev

up:
	@trap 'kill 0' SIGINT; \
	(cd server && uv run uvicorn dars.main:app --reload) & \
	(cd webapp && npm run dev) & \
	wait
