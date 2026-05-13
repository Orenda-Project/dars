-include .env
export

.PHONY: dev test db-new bruno-sync webapp up

dev:
	cd server && uv run uvicorn dars.main:app --reload

test:
	cd server && uv run pytest

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
