-include .env
export

.PHONY: dev test db-push db-pull db-status db-new db-link bruno-sync webapp

dev:
	cd api && uv run uvicorn dars.main:app --reload

test:
	cd api && uv run pytest

db-push:
	supabase db push

db-pull:
	supabase db pull

db-status:
	supabase migration list

db-new:
	@read -p "Migration name: " name; \
	supabase migration new $$name

db-link:
	supabase link --project-ref $(SUPABASE_PROJECT_REF)

bruno-sync:
	cd api && uv run python ../scripts/sync_bruno.py

webapp:
	cd webapp && npm run dev
