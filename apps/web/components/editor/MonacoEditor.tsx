"use client";
import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { api } from "@/lib/api";

const Editor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => <div className="p-3 text-xs text-gray-500">Loading editor...</div>,
});

export default function MonacoEditor({ projectId, path }: { projectId: string; path: string }) {
  const [value, setValue] = useState("");
  const [status, setStatus] = useState("Loading editor...");

  useEffect(() => {
    let live = true;
    setStatus("Loading file...");
    api<{ content: string }>(`/api/projects/${projectId}/file?path=${encodeURIComponent(path)}`)
      .then((file) => {
        if (live) {
          setValue(file.content);
          setStatus("");
        }
      })
      .catch(() => {
        if (live) {
          setValue(`# ${path}\n\nOpen a file from the explorer or ask an agent to edit it.`);
          setStatus("Preview fallback");
        }
      });
    return () => {
      live = false;
    };
  }, [projectId, path]);

  const language = path.endsWith(".py")
    ? "python"
    : path.endsWith(".ts") || path.endsWith(".tsx")
    ? "typescript"
    : "markdown";
  return (
    <div className="h-full">
      <div className="flex justify-between border-b border-gray-800 px-3 py-1 text-xs text-gray-400">
        <span>{path}</span>
        {status && <span>{status}</span>}
      </div>
      <Editor
        key={`${projectId}:${path}`}
        height="calc(100% - 26px)"
        theme="vs-dark"
        language={language}
        value={value}
        onChange={(next) => setValue(next ?? "")}
        options={{ fontSize: 13, minimap: { enabled: false }, automaticLayout: true }}
      />
    </div>
  );
}
