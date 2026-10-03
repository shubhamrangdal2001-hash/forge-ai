"""Codebase memory graph (differentiator #3).

Forge remembers what it has done to a repo: every completed run records the
goal, the files it touched, the outcome, and the key decisions as nodes/edges.
Future runs `recall()` similar past work so the planner doesn't relearn the
codebase each time — this is what makes Forge get *faster and more accurate the
longer it works on a project*, unlike stateless competitors.

Backed by Neo4j when available; falls back to a local JSON store under
`<project>/.forge/memory.json` so it works with zero infra in dev.
"""
from __future__ import annotations
import json
import os
import time
from .workspace import project_root

try:
    from .graph_store import GraphStore
    _graph = GraphStore()
except Exception:
    _graph = None


def _store_path(project_id: str) -> str:
    root = project_root(project_id)
    d = os.path.join(root, ".forge")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "memory.json")


def _load(project_id: str) -> list[dict]:
    try:
        with open(_store_path(project_id), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []


def _save(project_id: str, items: list[dict]) -> None:
    with open(_store_path(project_id), "w", encoding="utf-8") as f:
        json.dump(items[-500:], f, indent=2)  # cap local memory


def _keywords(text: str) -> set[str]:
    stop = {"the", "and", "for", "add", "with", "into", "this", "that"}
    words = "".join(c if c.isalnum() else " " for c in text).split()
    return {w.lower() for w in words if len(w) >= 3 and w.lower() not in stop}


def record(state) -> dict:
    """Persist a completed run as an experience node."""
    entry = {
        "run_id": state.run_id,
        "ts": time.time(),
        "goal": state.goal,
        "files": sorted({p.get("file_path") for p in state.patches if p.get("file_path")}),
        "outcome": "verified" if not state.failed else "halted",
        "iterations": state.iteration,
        "summary": (state.explanation or "")[:400],
    }
    items = _load(state.project_id)
    items.append(entry)
    _save(state.project_id, items)

    if _graph and getattr(_graph, "driver", None):
        try:
            with _graph.driver.session() as s:
                s.run(
                    "MERGE (r:Run {id:$id, project:$p}) SET r.goal=$g, r.outcome=$o "
                    "WITH r UNWIND $files AS fp "
                    "MERGE (f:File {path:fp, project:$p}) MERGE (r)-[:TOUCHED]->(f)",
                    id=entry["run_id"], p=state.project_id, g=entry["goal"],
                    o=entry["outcome"], files=entry["files"],
                )
        except Exception:
            pass
    return entry


def recall(project_id: str, goal: str, k: int = 5) -> list[dict]:
    """Return prior runs most relevant to the current goal (keyword overlap)."""
    items = _load(project_id)
    gk = _keywords(goal)
    scored = []
    for it in items:
        overlap = len(gk & _keywords(it.get("goal", "")))
        if overlap:
            scored.append((overlap, it))
    scored.sort(key=lambda x: (x[0], x[1].get("ts", 0)), reverse=True)
    return [it for _, it in scored[:k]]
