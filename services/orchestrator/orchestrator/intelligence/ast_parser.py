"""Tree-sitter based AST parsing -> symbol-aware chunks.

Chunk on function/class boundaries instead of fixed token windows so that
retrieval and graph edges line up with real code units.
"""
from dataclasses import dataclass

try:
    from tree_sitter_languages import get_parser
except Exception:  # optional at scaffold time
    get_parser = None

_LANG = {".py": "python", ".ts": "typescript", ".tsx": "tsx", ".js": "javascript"}


@dataclass
class Chunk:
    file_path: str
    symbol: str
    kind: str          # function|class|method|module
    start_line: int
    end_line: int
    code: str


def chunk_file(file_path: str, source: str) -> list[Chunk]:
    ext = "." + file_path.rsplit(".", 1)[-1]
    lang = _LANG.get(ext)
    if not lang or get_parser is None:
        return [Chunk(file_path, "<module>", "module", 1, source.count("\n") + 1, source)]
    parser = get_parser(lang)
    tree = parser.parse(source.encode())
    chunks: list[Chunk] = []
    wanted = {"function_definition", "class_definition", "method_definition", "function_declaration", "class_declaration"}
    cursor = tree.walk()

    def visit(node):
        if node.type in wanted:
            code = source.encode()[node.start_byte:node.end_byte].decode(errors="ignore")
            name = next((source.encode()[c.start_byte:c.end_byte].decode() for c in node.children if c.type == "identifier"), "<anon>")
            chunks.append(Chunk(file_path, name, node.type, node.start_point[0] + 1, node.end_point[0] + 1, code))
        for child in node.children:
            visit(child)

    visit(tree.root_node)
    return chunks or [Chunk(file_path, "<module>", "module", 1, source.count("\n") + 1, source)]
