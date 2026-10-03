"""Qdrant vector store for semantic code/doc retrieval."""
import os

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
except Exception:
    QdrantClient = None

_DIM = 1536


class VectorStore:
    def __init__(self):
        self.client = QdrantClient(url=os.getenv("QDRANT_URL", "http://localhost:6333")) if QdrantClient else None

    def ensure(self, project_id: str):
        if not self.client:
            return
        name = f"proj_{project_id}"
        if name not in {c.name for c in self.client.get_collections().collections}:
            self.client.create_collection(name, vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE))

    def upsert(self, project_id: str, points: list[dict]):
        if not self.client:
            return
        self.ensure(project_id)
        self.client.upsert(
            f"proj_{project_id}",
            [PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in points],
        )

    def search(self, project_id: str, vector: list[float], k: int = 8) -> list[dict]:
        if not self.client:
            return []
        res = self.client.search(f"proj_{project_id}", query_vector=vector, limit=k)
        return [{"score": r.score, **(r.payload or {})} for r in res]
