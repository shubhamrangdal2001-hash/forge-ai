"""Neo4j code graph: files, symbols, imports, calls, references.

Graph edges let the retriever expand from a hit to its callers/callees and
definitions — the structural half of hybrid retrieval.
"""
import os

try:
    from neo4j import GraphDatabase
except Exception:
    GraphDatabase = None


class GraphStore:
    def __init__(self):
        self.driver = (
            GraphDatabase.driver(
                os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "forgepass")),
            )
            if GraphDatabase else None
        )

    def add_symbol(self, project_id: str, file_path: str, symbol: str, kind: str):
        if not self.driver:
            return
        with self.driver.session() as s:
            s.run(
                "MERGE (f:File {path:$f, project:$p}) "
                "MERGE (sym:Symbol {name:$s, file:$f, project:$p}) "
                "SET sym.kind=$k MERGE (f)-[:DEFINES]->(sym)",
                f=file_path, s=symbol, k=kind, p=project_id,
            )

    def neighbors(self, project_id: str, symbol: str, depth: int = 1) -> list[dict]:
        if not self.driver:
            return []
        with self.driver.session() as s:
            rows = s.run(
                "MATCH (sym:Symbol {name:$s, project:$p})-[*1..$d]-(n:Symbol) "
                "RETURN DISTINCT n.name AS name, n.file AS file LIMIT 25",
                s=symbol, p=project_id, d=depth,
            )
            return [dict(r) for r in rows]
