"""Thin wrapper over ripgrep for fast lexical/regex search in the workspace."""
import json
import subprocess
from .workspace import project_root


def search(project_id: str, pattern: str, max_results: int = 50) -> list[dict]:
    root = project_root(project_id)
    try:
        proc = subprocess.run(
            ["rg", "--json", "-n", "--max-count", "5", pattern, str(root)],
            capture_output=True, text=True, timeout=20,
        )
    except FileNotFoundError:
        return []
    hits = []
    for line in proc.stdout.splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "match":
            d = ev["data"]
            hits.append({
                "file": d["path"]["text"],
                "line": d["line_number"],
                "text": d["lines"]["text"].strip(),
            })
        if len(hits) >= max_results:
            break
    return hits
