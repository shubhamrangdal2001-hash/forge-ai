# Deploy Forge Worldwide

This repo includes a production Docker Compose stack that runs the complete
Forge system behind a Caddy HTTPS edge:

- Next.js web UI
- FastAPI gateway
- Celery orchestrator worker
- PostgreSQL, Redis, Qdrant, and Neo4j
- Caddy reverse proxy with automatic HTTPS for a real domain

## 1. Prepare DNS and host

Use any cloud VM or container host that can run Docker and Docker Compose.
Create an `A` or `AAAA` record for your domain, for example:

```text
forge.example.com -> your-server-ip
```

Open inbound ports `80` and `443`. Caddy uses them for HTTP-to-HTTPS and TLS
certificate issuance.

## 2. Configure production secrets

```bash
cp .env.production.example .env.production
```

Edit `.env.production`:

- Set `DOMAIN`, `CORS_ORIGINS`, and `ALLOWED_HOSTS` to your public hostname.
- Replace every `CHANGE_ME` secret with a strong unique value.
- Set model API keys only for providers you want to enable.
- For NVIDIA AI, set `NVIDIA_API_KEY` or use the dashboard to validate and
  store a key in encrypted local storage. Optionally set
  `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`.
- Set `FORGE_STATE_DIR` to a persistent encrypted volume if using local
  credential storage and model discovery caches.
- If `POSTGRES_PASSWORD` contains URL-reserved characters, URL-encode it inside
  `DATABASE_URL`.

## 3. Build and start

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

Check status:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml ps
curl https://forge.example.com/health
```

The browser UI is served at `https://forge.example.com`. The frontend uses
same-origin `/api` and `/ws` by default, so it works cleanly behind Caddy,
Cloudflare, AWS ALB, or another HTTPS edge.

## 4. Global production notes

For a worldwide deployment, keep the web and gateway close to users and move
stateful services to managed infrastructure when traffic grows:

- Managed PostgreSQL with automated backups and point-in-time recovery.
- Managed Redis or a durable Redis-compatible service.
- Managed Qdrant and Neo4j, or dedicated regional instances.
- A CDN or global edge in front of Caddy/load balancer.
- Region-specific `CORS_ORIGINS` if you serve multiple public hostnames.
- Secret manager injection instead of checked-in `.env` files.
- A scheduled NVIDIA model refresh job that calls
  `POST /api/nvidia/models/refresh` after credentials are configured.
- Cloud upload policy review before sending repository context to NVIDIA or any
  external provider; keep `.git`, `node_modules`, `.env`, secrets, credentials,
  and generated build folders excluded by default.
- Centralized logs, metrics, alerts, and backup restore tests.

The worker mounts `/var/run/docker.sock` so it can run project verification in
containers. For higher-security production, replace that with an isolated
runner pool or remote sandbox service.

## 5. Update and rollback

Deploy a new version:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

View logs:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f gateway worker web caddy
```

Stop the stack:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml down
```
