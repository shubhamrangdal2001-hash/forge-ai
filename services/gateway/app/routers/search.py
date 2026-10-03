from fastapi import APIRouter
from ..schemas import SearchQuery

router = APIRouter(prefix="/api", tags=["search"])


@router.post("/search")
async def hybrid_search(body: SearchQuery):
    # Hybrid: ripgrep (lexical) + Qdrant (semantic) + Neo4j (structural) fused.
    from orchestrator.intelligence.retriever import hybrid_retrieve  # type: ignore
    hits = hybrid_retrieve(body.project_id, body.query, k=body.k)
    return {"query": body.query, "hits": hits}
