"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Project = {
  project_id: string;
  root: string;
  warnings?: string[];
};

export default function WelcomeScreen({ onSelect }: { onSelect: (project: Project) => void }) {
  const [path, setPath] = useState("");
  const [recent, setRecent] = useState<Project[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    api<Project[]>("/api/projects").then(setRecent).catch(() => setRecent([]));
  }, []);

  const selectWithDesktopDialog = async () => {
    const tauri = (window as unknown as { __TAURI__?: { dialog?: { open?: (opts: unknown) => Promise<string | null> } } }).__TAURI__;
    const picked = await tauri?.dialog?.open?.({ directory: true, multiple: false, title: "Select project folder" });
    if (typeof picked === "string") {
      setPath(picked);
      await selectProject(picked);
    } else if (path.trim()) {
      await selectProject(path);
    } else {
      const input = document.querySelector<HTMLInputElement>("[data-project-path]");
      input?.focus();
      setError("Type a project folder path, then open it.");
    }
  };

  const selectProject = async (targetPath = path) => {
    setError(null);
    const cleanPath = targetPath.trim();
    if (!cleanPath) {
      setError("Project folder path is required.");
      return;
    }
    setOpening(true);
    try {
      const project = await api<Project>("/api/projects/select", {
        method: "POST",
        body: JSON.stringify({ project_id: "demo", path: cleanPath }),
      });
      localStorage.setItem("forge.project", JSON.stringify(project));
      onSelect(project);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not select project folder.");
    } finally {
      setOpening(false);
    }
  };

  return (
    <div className="min-h-screen bg-black text-gray-100">
      <div className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center gap-8 px-6">
        <div className="space-y-3">
          <div className="text-[11px] uppercase tracking-wide text-gray-500">Forge Desktop IDE</div>
          <h1 className="text-4xl font-semibold tracking-normal">Select a project folder</h1>
          <p className="max-w-2xl text-sm leading-6 text-gray-400">
            Forge will treat this folder as the only workspace root. Agent reads, staged diffs, backups, and approved saves stay inside it.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-[1fr_240px]">
          <div className="rounded border border-gray-800 bg-forge-panel p-4">
            <div className="space-y-3">
              <label className="text-xs text-gray-400" htmlFor="project-path">Project folder path</label>
              <input
                id="project-path"
                data-project-path
                data-testid="project-path-input"
                className="w-full rounded border border-gray-700 bg-black px-3 py-2 text-sm"
                placeholder="D:\Projects\my-app"
                value={path}
                onChange={(event) => setPath(event.target.value)}
              />
              {error && <div className="text-xs text-red-400">{error}</div>}
              <div className="flex flex-wrap gap-2">
                <button
                  data-testid="select-project-folder-button"
                  onClick={selectWithDesktopDialog}
                  disabled={opening}
                  className="rounded bg-forge-accent px-3 py-2 text-xs font-medium text-white disabled:bg-gray-800"
                >
                  {opening ? "Opening..." : "Select project folder"}
                </button>
                <button
                  data-testid="open-typed-path-button"
                  onClick={() => selectProject()}
                  disabled={opening}
                  className="rounded border border-gray-700 px-3 py-2 text-xs text-gray-200 disabled:text-gray-600"
                >
                  {opening ? "Opening..." : "Open typed path"}
                </button>
              </div>
            </div>
          </div>

          <div className="rounded border border-gray-800 bg-forge-panel p-4">
            <div className="mb-3 text-[11px] uppercase tracking-wide text-gray-500">Recent projects</div>
            <div className="space-y-2">
              {recent.length === 0 && <div className="text-xs text-gray-500">No recent projects yet.</div>}
              {recent.map((project) => (
                <button
                  key={`${project.project_id}:${project.root}`}
                  onClick={() => {
                    localStorage.setItem("forge.project", JSON.stringify(project));
                    onSelect(project);
                  }}
                  className="block w-full rounded border border-gray-800 bg-black px-2 py-2 text-left text-xs text-gray-200 hover:border-gray-600"
                >
                  <div className="font-medium">{project.project_id}</div>
                  <div className="truncate text-gray-500">{project.root}</div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid gap-3 text-xs text-gray-400 md:grid-cols-3">
          <div className="rounded border border-gray-800 bg-forge-panel p-3">All paths are normalized before reads or writes.</div>
          <div className="rounded border border-gray-800 bg-forge-panel p-3">Generated code is shown as a diff before saving.</div>
          <div className="rounded border border-gray-800 bg-forge-panel p-3">Backups are created before approved risky edits.</div>
        </div>
      </div>
    </div>
  );
}
