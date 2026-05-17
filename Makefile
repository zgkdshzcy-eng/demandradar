# Convenience targets. Run from repo root.
# `make help` to list targets.

SHELL := bash
.DEFAULT_GOAL := help
COMPOSE_DEV  := docker compose -f backend/docker-compose.yml
COMPOSE_PROD := docker compose --env-file .env.prod -f docker-compose.prod.yml

help: ## list available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | sort \
	  | awk -F':.*?## ' '{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ---------- dev ----------
dev-up: ## start postgres+redis (dev) in the background
	$(COMPOSE_DEV) up -d
dev-down: ## stop dev infra
	$(COMPOSE_DEV) down
dev-logs: ## tail dev infra logs
	$(COMPOSE_DEV) logs -f --tail 100

api: ## run backend api locally (uvicorn --reload)
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
worker: ## run scheduler worker locally
	cd backend && python -m app.worker
web: ## run frontend dev server
	cd frontend && npm run dev

# ---------- tests ----------
test: ## backend pytest
	cd backend && pytest -q
lint: ## ruff + next lint
	cd backend && ruff check app tests
	cd frontend && npm run lint --silent || true

# ---------- migrations ----------
migrate: ## alembic upgrade head
	cd backend && alembic upgrade head
revision: ## alembic autogenerate (usage: make revision m="message")
	cd backend && alembic revision --autogenerate -m "$(m)"

# ---------- prod ----------
prod-build: ## build api+web images locally
	$(COMPOSE_PROD) build
prod-up: ## bring up the prod stack on this host (requires .env.prod)
	$(COMPOSE_PROD) up -d
prod-down: ## stop the prod stack
	$(COMPOSE_PROD) down
prod-logs: ## tail prod logs
	$(COMPOSE_PROD) logs -f --tail 200
prod-ps: ## prod service status
	$(COMPOSE_PROD) ps
prod-restart: ## restart api+worker+web (no DB downtime)
	$(COMPOSE_PROD) up -d --no-deps --build api worker web

# ---------- one-off cli ----------
cli-stats: ## inspect data volume on the prod stack
	$(COMPOSE_PROD) exec api python -m app.cli stats
issue-code: ## issue a redeem code: make issue-code plan=weekly_pro days=30
	$(COMPOSE_PROD) exec api python -m app.cli billing issue-code --plan $(plan) --days $(days)

.PHONY: help dev-up dev-down dev-logs api worker web test lint migrate revision \
        prod-build prod-up prod-down prod-logs prod-ps prod-restart \
        cli-stats issue-code
