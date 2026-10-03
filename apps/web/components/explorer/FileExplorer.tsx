"use client";
import { useEffect, useState, CSSProperties } from "react";
import { api } from "@/lib/api";

type Node = { path: string; type: "file" | "dir"; children?: Node[] };

const indent = (depth: number): CSSProperties => ({ paddingLeft: 8 + depth * 12 });

export default function FileExplorer({ projectId, onOpen }: { projectId: string; onOpen: (p: string) => void }) {
  const [tree, setTree] = useState<Node[]>([]);
  useEffect(() => {
    api<Node[]>(`/api/projects/${projectId}/tree`)
      .then(setTree)
      .catch(() =>
        setTree([
          { path: "README.md", type: "file" },
          { path: "services", type: "dir", children: [{ path: "services/gateway/app/main.py", type: "file" }] },
        ]),
      );
  }, [projectId]);

  const render = (nodes: Node[], depth = 0): JSX.Element[] =>
    nodes.map((n) => (
      <div key={n.path}>
        <button
          className="block w-full text-left px-2 py-0.5 text-xs hover:bg-gray-800"
          style={indent(depth)}
          onClick={() => n.type === "file" && onOpen(n.path)}
        >
          {n.type === "dir" ? "\uD83D\uDCC1" : "\uD83D\uDCC4"} {n.path.split("/").pop()}
        </button>
        {n.children && render(n.children, depth + 1)}
      </div>
    ));

  return (
    <div>
      <div className="px-2 py-2 text-[11px] uppercase tracking-wide text-gray-500">Explorer</div>
      {render(tree)}
    </div>
  );
}
