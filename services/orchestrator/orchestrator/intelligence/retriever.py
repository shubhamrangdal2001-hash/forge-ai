"""Hybrid retrieval = lexical (ripgrep) + semantic (Qdrant) + structural (Neo4j).

Results are fused with reciprocal-rank fusion (RRF), then graph-expanded so
the agent sees definitions and callers, not just text matches. This is the
core anti-hallucination mechanism: every answer is grounded in real code.
"""
from .ripgrep import search as rg_search
from .vector_store import VectorStore
from .graph_store import GraphStore

_vec = VectorStore()
_graph = GraphStore()


def _embed(text: str) -> list[float]:
    # Plug in your embedding model (e.g. local bge-code / text-embedding-3).
    return [0.0] * 1536


def _rrf(rankings: list[list[str]], k: int = 60) -> dict[str, float]:
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, key in enumerate(ranking):
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    return scores


def hybrid_retrieve(project_id: str, query: str, k: int = 8) -> list[dict]:
    lexical = rg_search(project_id, query, max_results=k * 2)
    semantic = _vec.search(project_id, _embed(query), k=k * 2)

    lex_keys = [h["file"] for h in lexical]
    sem_keys = [h.get("file_path", "") for h in semantic]
    fused = _rrf([lex_keys, sem_keys])

    ranked = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)[:k]
    results = [{"file": f, "score": sc} for f, sc in ranked]

    # Structural expansion: pull neighbors of the top hit.
    if results:
        top_symbol = results[0]["file"].split("/")[-1].split(".")[0]
        results.append({"neighbors": _graph.neighbors(project_id, top_symbol)})
    return results
