"""Repo indexer: walk -> AST chunk -> embed -> Qdrant + Neo4j."""
import os
from .workspace import project_root
from .ast_parser import chunk_file
from .vector_store import VectorStore
from .graph_store import GraphStore
from .retriever import _embed

_SKIP = {".git", "node_modules", ".next", "__pycache__", "dist", "build"}


def index_project(project_id: str) -> dict:
    root = project_root(project_id)
    vec, graph = VectorStore(), GraphStore()
    vec.ensure(project_id)
    n_chunks = 0
    points = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in _SKIP]
        for fn in files:
            if not fn.endswith((".py", ".ts", ".tsx", ".js")):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            try:
                src = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for ch in chunk_file(rel, src):
                graph.add_symbol(project_id, rel, ch.symbol, ch.kind)
                points.append({
                    "id": n_chunks,
                    "vector": _embed(ch.code),
                    "payload": {"file_path": rel, "symbol": ch.symbol, "start": ch.start_line},
                })
                n_chunks += 1
    vec.upsert(project_id, points)
    return {"project_id": project_id, "chunks": n_chunks}
