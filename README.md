# Forge — AI-Native Coding Platform (Starter Repo)

A runnable scaffold for an agent-first, verification-driven coding IDE/agent platform.

## Stack
- **Frontend:** Next.js + Monaco Editor + xterm.js + file explorer + agent dashboard
- **Backend:** FastAPI + WebSocket + Celery/RQ workers
- **Agent Engine:** Custom DAG orchestrator (LangGraph-ready)
- **Models:** Bring-your-own, model-agnostic. The user picks any popular coding model worldwide per agent role, including **NVIDIA AI** through the NVIDIA Inference/NIM API, **Anthropic**, **OpenAI-compatible providers**, **Google**, **xAI**, **Cohere**, **Moonshot Kimi**, **DeepSeek**, **Alibaba Qwen**, **Mistral/Codestral**, **Meta Llama** via Groq/Together, **OpenRouter**, and fully **local** models via **Ollama / LM Studio**. Smart per-task defaults are used when nothing is chosen.
- **Code Intelligence:** Tree-sitter · ripgrep · LSP · Qdrant (vector) · Neo4j (graph) · Postgres (relational)
- **Execution:** Docker sandbox per project · pytest/jest/mypy/eslint/ruff/build runner
- **Reliability loop:** Plan → Patch → Test → Verify → Explain → Rollback

## Quick start
```bash
cp .env.example .env          # add your model API keys
docker compose up -d          # postgres, redis, qdrant, neo4j

# Backend
cd services/gateway && pip install -r requirements.txt && uvicorn app.main:app --reload
# Worker
cd services/orchestrator && pip install -r requirements.txt && celery -A orchestrator.celery_app worker -l info
# Frontend
cd apps/web && npm install && npm run dev
```
Open http://localhost:3000 — editor + terminal + agent dashboard.

## Production deploy
Forge includes a production Compose stack for a public HTTPS deployment:

```bash
cp .env.production.example .env.production
# edit .env.production with your domain, strong secrets, and model keys
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Caddy serves the app at `https://$DOMAIN`, routes `/api` and `/ws` to the
gateway, and terminates TLS automatically. See `docs/DEPLOYMENT.md` for the
full worldwide deployment checklist.

## Choosing models
Forge is model-agnostic. Set API keys only for the providers you want in `.env`
(any provider without a key is skipped). In the agent dashboard, use the **model
picker** to choose either one model for everything or a different model per role
(Planner, Coder, Reviewer, …). Toggle **Local only** to run fully offline on
Ollama/LM Studio with zero cloud keys and zero cost. The full catalog is served
at `GET /api/models`; add a new model by adding one entry to
`services/orchestrator/orchestrator/models/providers.py` — nothing else changes.

## NVIDIA AI
Use the NVIDIA AI panel in the dashboard to validate and store a NVIDIA API key,
refresh account-visible models, favorite or pin defaults, benchmark models, and
compare capabilities. Forge discovers NVIDIA models live from the account and
does not ship a hardcoded free-model list. New modes include `nvidia_only`,
`hybrid`, and `cloud_fallback`.

## Layout
```
apps/web            Next.js UI (Monaco, xterm.js, explorer, dashboard)
services/gateway    FastAPI REST + WebSocket
services/orchestrator  Agent DAG engine, model router, code intel, sandbox, verifiers
db                  Postgres schema + migrations
```
See `docs/ARCHITECTURE.md` for the full design.
See `docs/AI_NATIVE_IDE_UPGRADE.md` for the local-model manager, hardware tiers,
smart router, safety plan, benchmark plan, and roadmap toward a Cursor/Kimi
Work/Antigravity-class AI coding IDE.
See `docs/NVIDIA_AI_PROVIDER.md` for NVIDIA provider architecture, security,
model discovery, API flows, testing, and deployment.
See `docs/DESKTOP_IDE_PLAN.md` for the downloadable desktop app architecture,
selected-folder boundary model, and permission-before-save workflow.
