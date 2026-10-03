"use client";
import { useEffect, useState } from "react";
import FileExplorer from "@/components/explorer/FileExplorer";
import MonacoEditor from "@/components/editor/MonacoEditor";
import Terminal from "@/components/terminal/Terminal";
import AgentDashboard from "@/components/dashboard/AgentDashboard";
import AgentOutput from "@/components/dashboard/AgentOutput";
import CostDashboard from "@/components/dashboard/CostDashboard";
import VerificationReport from "@/components/dashboard/VerificationReport";
import WelcomeScreen from "@/components/workspace/WelcomeScreen";

type Project = {
  project_id: string;
  root: string;
  warnings?: string[];
};

export default function Home() {
  const [activeFile, setActiveFile] = useState<string>("README.md");
  const [runId, setRunId] = useState<string | null>(null);
  const [project, setProject] = useState<Project | null>(null);

  useEffect(() => {
    const raw = localStorage.getItem("forge.project");
    if (raw) {
      try {
        setProject(JSON.parse(raw));
      } catch {
        localStorage.removeItem("forge.project");
      }
    }
  }, []);

  if (!project) {
    return <WelcomeScreen onSelect={setProject} />;
  }

  return (
    <div className="grid h-screen grid-cols-[220px_minmax(280px,1fr)_360px] grid-rows-[1fr_250px] overflow-hidden bg-forge-bg text-gray-100">
      <aside className="row-span-2 border-r border-gray-800 bg-forge-panel overflow-auto">
        <div className="border-b border-gray-800 px-2 py-2">
          <div className="text-[11px] uppercase tracking-wide text-gray-500">Workspace</div>
          <div className="truncate text-xs text-gray-300" title={project.root}>{project.root}</div>
          <button
            className="mt-1 text-[11px] text-gray-500 hover:text-gray-300"
            onClick={() => {
              localStorage.removeItem("forge.project");
              setProject(null);
              setRunId(null);
            }}
          >
            Change folder
          </button>
        </div>
        <FileExplorer projectId={project.project_id} onOpen={setActiveFile} />
      </aside>
      <main className="overflow-hidden">
        <MonacoEditor projectId={project.project_id} path={activeFile} />
      </main>
      <section className="row-span-2 border-l border-gray-800 bg-forge-panel overflow-auto">
        <AgentDashboard projectId={project.project_id} onRunId={setRunId} />
        <AgentOutput projectId={project.project_id} runId={runId} />
        <VerificationReport runId={runId} />
        <CostDashboard runId={runId} />
      </section>
      <footer className="bg-black">
        <Terminal projectId={project.project_id} projectRoot={project.root} />
      </footer>
    </div>
  );
}
