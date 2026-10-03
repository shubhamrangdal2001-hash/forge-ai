.PHONY: up down gateway worker web fmt

up:
	docker compose up -d

down:
	docker compose down

gateway:
	cd services/gateway && uvicorn app.main:app --reload --port 8000

worker:
	cd services/orchestrator && celery -A orchestrator.celery_app worker -l info

web:
	cd apps/web && npm run dev
