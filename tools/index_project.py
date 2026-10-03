#!/usr/bin/env python3
"""Forge project indexer (dependency-free).

Produces a single index.json containing:
  1. file chunks        — symbol-aligned slices (fallback: line windows)
  2. AST symbols        — functions / classes / methods with signatures + docstrings
  3. imports            — per-file import statements
  4. functions          — flat list (kind=function|method)
  5. classes            — flat list (kind=class)
  6. dependency graph   — module -> module edges, internal vs external
  7. README / docs      — markdown files with parsed headings + module docstrings

Python is parsed with the stdlib `ast`. JS/TS/JSX use light regex extraction so
the tool runs anywhere with zero third-party deps. Swap in tree-sitter later for
full-fidelity JS/TS without changing the output schema.

Usage:  python3 tools/index_project.py [REPO_ROOT] [-o index.json]
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone

SKIP_DIRS = {".git", "node_modules", ".next", "__pycache__", "dist", "build", ".venv", "venv"}
CODE_EXT = {".py", ".ts", ".tsx", ".js", ".jsx"}
DOC_EXT = {".md", ".mdx", ".rst", ".txt"}
WINDOW = 60  # fallback chunk size in lines


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #
@dataclass
class Symbol:
    id: str
    name: str
    kind: str            # function | method | class
    file: str
    start_line: int
    end_line: int
    signature: str = ""
    docstring: str | None = None
    parent: str | None = None


@dataclass
class Chunk:
    id: str
    file: str
    kind: str            # symbol | window
    symbol: str | None
    start_line: int
    end_line: int
    sha: str


@dataclass
class FileRecord:
    path: str
    language: str
    loc: int
    sha: str
    module: str
    doc: str | None = None
    imports: list[dict] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)  # symbol ids
    chunks: list[str] = field(default_factory=list)    # chunk ids


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def sha8(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:8]


def lang_for(path: str) -> str:
    ext = os.path.splitext(path)[1]
    return {
        ".py": "python", ".ts": "typescript", ".tsx": "tsx",
        ".js": "javascript", ".jsx": "jsx", ".md": "markdown",
        ".mdx": "markdown", ".rst": "rst", ".txt": "text",
    }.get(ext, "text")


def module_name(rel_path: str) -> str:
    """Map a repo-relative path to a dotted module-ish name."""
    no_ext = os.path.splitext(rel_path)[0]
    return no_ext.replace(os.sep, ".").replace("/", ".")


def window_chunks(rel: str, lines: list[str]) -> list[Chunk]:
    out: list[Chunk] = []
    for start in range(0, len(lines), WINDOW):
        seg = lines[start:start + WINDOW]
        body = "\n".join(seg)
        out.append(Chunk(
            id=f"{rel}#L{start + 1}", file=rel, kind="window", symbol=None,
            start_line=start + 1, end_line=start + len(seg), sha=sha8(body),
        ))
    return out


# --------------------------------------------------------------------------- #
# Python extraction (stdlib ast)
# --------------------------------------------------------------------------- #
def extract_python(rel: str, source: str):
    symbols: list[Symbol] = []
    imports: list[dict] = []
    module_doc = None
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return symbols, imports, module_doc, [{"error": str(e)}]

    module_doc = ast.get_docstring(tree)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imports.append({"type": "import", "module": a.name, "alias": a.asname})
        elif isinstance(node, ast.ImportFrom):
            mod = ("." * (node.level or 0)) + (node.module or "")
            for a in node.names:
                imports.append({"type": "from", "module": mod, "name": a.name, "alias": a.asname})

    def sig(fn) -> str:
        try:
            return "(" + ", ".join(
                getattr(arg, "arg", "") for arg in fn.args.args
            ) + ")"
        except Exception:
            return "()"

    def end_of(node) -> int:
        return getattr(node, "end_lineno", node.lineno) or node.lineno

    def visit(node, parent_name=None):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                kind = "method" if parent_name else "function"
                sym = Symbol(
                    id=f"{rel}::{(parent_name + '.') if parent_name else ''}{child.name}",
                    name=child.name, kind=kind, file=rel,
                    start_line=child.lineno, end_line=end_of(child),
                    signature=child.name + sig(child),
                    docstring=ast.get_docstring(child), parent=parent_name,
                )
                symbols.append(sym)
                visit(child, parent_name)  # nested functions
            elif isinstance(child, ast.ClassDef):
                sym = Symbol(
                    id=f"{rel}::{child.name}", name=child.name, kind="class", file=rel,
                    start_line=child.lineno, end_line=end_of(child),
                    signature="class " + child.name,
                    docstring=ast.get_docstring(child), parent=parent_name,
                )
                symbols.append(sym)
                visit(child, child.name)  # methods
            else:
                visit(child, parent_name)

    visit(tree)
    return symbols, imports, module_doc, []


# --------------------------------------------------------------------------- #
# JS / TS extraction (regex, best-effort)
# --------------------------------------------------------------------------- #
RE_IMPORT = re.compile(r"""import\s+(?:[\w*{}\s,]+\s+from\s+)?['\"]([^'\"]+)['\"]""")
RE_REQUIRE = re.compile(r"""require\(\s*['\"]([^'\"]+)['\"]\s*\)""")
RE_FUNC = re.compile(r"""(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)""")
RE_ARROW = re.compile(r"""(?:export\s+)?const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>""")
RE_CLASS = re.compile(r"""(?:export\s+)?class\s+([A-Za-z_$][\w$]*)""")


def extract_js(rel: str, source: str):
    symbols: list[Symbol] = []
    imports: list[dict] = []
    lines = source.splitlines()

    for m in RE_IMPORT.finditer(source):
        imports.append({"type": "import", "module": m.group(1)})
    for m in RE_REQUIRE.finditer(source):
        imports.append({"type": "require", "module": m.group(1)})

    def line_of(pos: int) -> int:
        return source.count("\n", 0, pos) + 1

    for regex, kind in ((RE_FUNC, "function"), (RE_ARROW, "function"), (RE_CLASS, "class")):
        for m in regex.finditer(source):
            ln = line_of(m.start())
            symbols.append(Symbol(
                id=f"{rel}::{m.group(1)}@{ln}", name=m.group(1), kind=kind, file=rel,
                start_line=ln, end_line=ln, signature=m.group(0).strip(),
            ))
    return symbols, imports, None, []


# --------------------------------------------------------------------------- #
# Docs extraction
# --------------------------------------------------------------------------- #
def extract_doc(rel: str, source: str) -> dict:
    headings = []
    for i, line in enumerate(source.splitlines(), 1):
        m = re.match(r"^(#{1,6})\s+(.*)", line)
        if m:
            headings.append({"level": len(m.group(1)), "text": m.group(2).strip(), "line": i})
    title = headings[0]["text"] if headings else os.path.basename(rel)
    return {"path": rel, "title": title, "headings": headings}


# --------------------------------------------------------------------------- #
# Symbol-aligned chunking
# --------------------------------------------------------------------------- #
def symbol_chunks(rel: str, lines: list[str], symbols: list[Symbol]) -> list[Chunk]:
    if not symbols:
        return window_chunks(rel, lines)
    chunks: list[Chunk] = []
    for s in symbols:
        if s.kind == "method":
            continue  # methods are covered by their class chunk
        seg = "\n".join(lines[s.start_line - 1:s.end_line])
        chunks.append(Chunk(
            id=f"{rel}::{s.name}", file=rel, kind="symbol", symbol=s.name,
            start_line=s.start_line, end_line=s.end_line, sha=sha8(seg),
        ))
    if not chunks:
        return window_chunks(rel, lines)
    return chunks


# --------------------------------------------------------------------------- #
# Dependency graph
# --------------------------------------------------------------------------- #
def build_dependency_graph(files: dict[str, FileRecord]):
    modules = {fr.module: fr.path for fr in files.values()}
    py_index: dict[str, str] = {}
    for fr in files.values():
        if fr.language == "python":
            py_index[fr.module] = fr.path
            py_index[fr.module.split(".")[-1]] = fr.path  # last component too

    nodes = sorted({fr.module for fr in files.values()})
    edges = []
    seen = set()
    for fr in files.values():
        for imp in fr.imports:
            target_mod = imp.get("module", "") or ""
            resolved = None
            # internal python resolution
            base = target_mod.lstrip(".")
            for cand in (base, base.split(".")[-1] if base else ""):
                if cand and cand in py_index:
                    resolved = module_name(py_index[cand])
                    break
            # internal JS relative import resolution
            if resolved is None and target_mod.startswith("."):
                guess = os.path.normpath(os.path.join(os.path.dirname(fr.path), target_mod))
                for ext in ("", ".ts", ".tsx", ".js", ".jsx", "/index.ts", "/index.tsx"):
                    cand_path = guess + ext
                    if cand_path in files:
                        resolved = files[cand_path].module
                        break
            external = resolved is None
            to = resolved if resolved else (target_mod or "<unknown>")
            key = (fr.module, to, external)
            if key in seen:
                continue
            seen.add(key)
            edges.append({"from": fr.module, "to": to, "external": external})
    return {"nodes": nodes, "edges": edges}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def index_project(root: str) -> dict:
    files: dict[str, FileRecord] = {}
    all_symbols: dict[str, Symbol] = {}
    all_chunks: dict[str, Chunk] = {}
    docs: list[dict] = []
    errors: list[dict] = []

    for dirpath, dirs, filenames in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in filenames:
            abs_path = os.path.join(dirpath, fn)
            rel = os.path.relpath(abs_path, root).replace(os.sep, "/")
            ext = os.path.splitext(fn)[1]
            if ext not in CODE_EXT and ext not in DOC_EXT:
                continue
            try:
                source = open(abs_path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            lines = source.splitlines()

            if ext in DOC_EXT:
                docs.append(extract_doc(rel, source))
                # docs still get a file record + window chunks for retrieval
                fr = FileRecord(path=rel, language=lang_for(rel), loc=len(lines),
                                sha=sha8(source), module=module_name(rel))
                for c in window_chunks(rel, lines):
                    all_chunks[c.id] = c
                    fr.chunks.append(c.id)
                files[rel] = fr
                continue

            if ext == ".py":
                syms, imports, doc, errs = extract_python(rel, source)
            else:
                syms, imports, doc, errs = extract_js(rel, source)
            errors.extend({"file": rel, **e} for e in errs)

            fr = FileRecord(path=rel, language=lang_for(rel), loc=len(lines),
                            sha=sha8(source), module=module_name(rel), doc=doc,
                            imports=imports)
            for s in syms:
                all_symbols[s.id] = s
                fr.symbols.append(s.id)
            for c in symbol_chunks(rel, lines, syms):
                all_chunks[c.id] = c
                fr.chunks.append(c.id)
            files[rel] = fr

    dep_graph = build_dependency_graph(files)

    funcs = [asdict(s) for s in all_symbols.values() if s.kind in ("function", "method")]
    classes = [asdict(s) for s in all_symbols.values() if s.kind == "class"]

    index = {
        "project": os.path.basename(os.path.abspath(root)),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stats": {
            "files": len(files),
            "chunks": len(all_chunks),
            "symbols": len(all_symbols),
            "functions": len(funcs),
            "classes": len(classes),
            "imports": sum(len(fr.imports) for fr in files.values()),
            "dep_edges": len(dep_graph["edges"]),
            "dep_edges_internal": sum(1 for e in dep_graph["edges"] if not e["external"]),
            "docs": len(docs),
        },
        "files": [asdict(fr) for fr in sorted(files.values(), key=lambda f: f.path)],
        "symbols": [asdict(s) for s in all_symbols.values()],
        "functions": funcs,
        "classes": classes,
        "chunks": [asdict(c) for c in all_chunks.values()],
        "dependency_graph": dep_graph,
        "docs": docs,
        "errors": errors,
    }
    return index


def print_summary(index: dict) -> None:
    s = index["stats"]
    print(f"\n◈ Forge index — project '{index['project']}'")
    print("  " + "-" * 46)
    for label, key in [
        ("Files indexed", "files"), ("Chunks", "chunks"), ("Symbols", "symbols"),
        ("  └ functions/methods", "functions"), ("  └ classes", "classes"),
        ("Imports", "imports"), ("Dependency edges", "dep_edges"),
        ("  └ internal", "dep_edges_internal"), ("Docs (md/rst/txt)", "docs"),
    ]:
        print(f"  {label:<26} {s[key]}")
    print("  " + "-" * 46)
    print("  Top internal dependencies:")
    internal = [e for e in index["dependency_graph"]["edges"] if not e["external"]]
    for e in internal[:8]:
        print(f"    {e['from']}  ->  {e['to']}")
    if not internal:
        print("    (none resolved)")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Forge project indexer")
    ap.add_argument("root", nargs="?", default=".", help="repo root to index")
    ap.add_argument("-o", "--out", default="index.json", help="output JSON path")
    args = ap.parse_args(argv)

    index = index_project(args.root)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    print_summary(index)
    print(f"\n  Wrote {args.out} ({os.path.getsize(args.out) // 1024} KB)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
