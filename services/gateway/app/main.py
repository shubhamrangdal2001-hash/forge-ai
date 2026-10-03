from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from .config import settings
from .routers import projects, runs, diffs, search, metrics, models, local_models, nvidia, terminal
from .ws import router as ws_router

app = FastAPI(title="Forge Gateway", version="0.1.0")

if settings.allowed_hosts != ["*"]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router)
app.include_router(runs.router)
app.include_router(diffs.router)
app.include_router(search.router)
app.include_router(metrics.router)
app.include_router(models.router)
app.include_router(local_models.router)
app.include_router(nvidia.router)
app.include_router(terminal.router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
