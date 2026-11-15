.PHONY: install dev-api dev-web test test-api test-web e2e build migrate seed-demo up down

install:
	python -m venv .venv && . .venv/bin/activate && pip install -r backend/requirements.txt
	cd frontend && npm ci

migrate:
	cd backend && alembic upgrade head

seed-demo:
	cd backend && python -m app.cli seed-demo

dev-api:
	cd backend && uvicorn app.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

test: test-api test-web

test-api:
	cd backend && python -m pytest tests -q --cov=app

test-web:
	cd frontend && npm run typecheck && npm test

e2e:
	cd frontend && npm run e2e

build:
	cd frontend && npm run build

up:
	docker compose up --build -d

down:
	docker compose down
