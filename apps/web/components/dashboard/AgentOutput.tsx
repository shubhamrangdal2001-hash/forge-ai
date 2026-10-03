"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Artifact = {
  file_path: string;
  content: string;
  truncated?: boolean;
};

type Patch = {
  file_path: string;
  patch: string;
};

type TerminalResult = {
  command: string;
  cwd: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  timed_out: boolean;
};

type Report = {
  verdict: string;
  goal?: string;
  explanation?: string | null;
  files_changed?: string[];
  model_output_errors?: { task?: string; model?: string; reason?: string; preview?: string }[];
  artifacts?: Artifact[];
  patches?: Patch[];
  risk_level?: string;
  risk_reasons?: string[];
  requires_save_approval?: boolean;
};

type StagedDiff = {
  id: string;
  status: string;
  applied_files?: string[];
  backups?: string[];
};

type Runner = {
  label: string;
  command: string;
};

const SAFE_RUN_PATH = /^[A-Za-z0-9_./\\() -]+$/;

function psQuote(value: string) {
  return `'${value.replace(/'/g, "''")}'`;
}

function runnerFor(filePath: string): Runner | null {
  if (!SAFE_RUN_PATH.test(filePath)) return null;
  const normalized = filePath.replace(/\\/g, "/");
  const parts = normalized.split("/");
  const fileName = parts[parts.length - 1] ?? "";
  const folder = parts.slice(0, -1).join("/") || ".";
  const stem = fileName.replace(/\.[^.]+$/, "");
  const safeStem = stem.replace(/[^A-Za-z0-9_.-]/g, "_") || "program";
  const ext = fileName.split(".").pop()?.toLowerCase();

  if (ext === "py") {
    return { label: "Run Python", command: `python ${psQuote(normalized)}` };
  }
  if (ext === "js") {
    return { label: "Run Node", command: `node ${psQuote(normalized)}` };
  }
  if (ext === "c") {
    const exe = `.forge-run/${safeStem}.exe`;
    return {
      label: "Compile + run C",
      command: `if (!(Test-Path '.forge-run')) { New-Item -ItemType Directory '.forge-run' | Out-Null }; gcc ${psQuote(normalized)} -o ${psQuote(exe)}; if ($LASTEXITCODE -eq 0) { & ${psQuote(exe)} }`,
    };
  }
  if (ext === "cpp" || ext === "cc" || ext === "cxx") {
    const exe = `.forge-run/${safeStem}.exe`;
    return {
      label: "Compile + run C++",
      command: `if (!(Test-Path '.forge-run')) { New-Item -ItemType Directory '.forge-run' | Out-Null }; g++ ${psQuote(normalized)} -o ${psQuote(exe)}; if ($LASTEXITCODE -eq 0) { & ${psQuote(exe)} }`,
    };
  }
  if (ext === "java") {
    const className = stem.replace(/[^A-Za-z0-9_$]/g, "");
    if (!/^[A-Za-z_$][A-Za-z0-9_$]*$/.test(className)) return null;
    return {
      label: "Compile + run Java",
      command: `javac ${psQuote(normalized)}; if ($LASTEXITCODE -eq 0) { java -cp ${psQuote(folder)} ${className} }`,
    };
  }
  return null;
}

export default function AgentOutput({ projectId, runId }: { projectId: string; runId: string | null }) {
  const [report, setReport] = useState<Report | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [backup, setBackup] = useState(true);
  const [saveStatus, setSaveStatus] = useState<string | null>(null);
  const [savedFiles, setSavedFiles] = useState<string[]>([]);
  const [runStatus, setRunStatus] = useState<{ file: string; result?: TerminalResult; error?: string } | null>(null);

  useEffect(() => {
    setReport(null);
    setSelectedFiles([]);
    setSaveStatus(null);
    setSavedFiles([]);
    setRunStatus(null);
    if (!runId) return;
    let live = true;
    const load = async () => {
      try {
        const next = await api<Report>(`/api/runs/${runId}/report`);
        if (live) {
          setReport(next);
          if (next.files_changed?.length) setSelectedFiles((current) => current.length ? current : next.files_changed ?? []);
        }
      } catch {
        /* report is created at the end of the run */
      }
    };
    load();
    const timer = setInterval(load, 1500);
    return () => {
      live = false;
      clearInterval(timer);
    };
  }, [runId]);

  const toggleFile = (file: string) => {
    setSelectedFiles((current) => (
      current.includes(file) ? current.filter((item) => item !== file) : [...current, file]
    ));
  };

  const stage = async () => {
    if (!report?.patches?.length) throw new Error("No patches to save.");
    return api<StagedDiff>("/api/diffs/stage", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, patches: report.patches }),
    });
  };

  const approveSave = async () => {
    setSaveStatus("Preparing approved save...");
    try {
      const staged = await stage();
      const saved = await api<StagedDiff>(`/api/diffs/${staged.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ accepted: true, backup, selected_files: selectedFiles }),
      });
      setSavedFiles(saved.applied_files ?? []);
      setSaveStatus(`Saved ${saved.applied_files?.length ?? 0} file(s). Backup files: ${saved.backups?.length ?? 0}.`);
    } catch (err) {
      setSaveStatus(err instanceof Error ? err.message : "Save failed.");
    }
  };

  const rejectSave = async () => {
    setSaveStatus("Rejected. No files were written.");
  };

  const runSavedFile = async (file: string) => {
    const runner = runnerFor(file);
    if (!runner) return;
    setRunStatus({ file });
    try {
      const result = await api<TerminalResult>("/api/terminal/run", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, command: runner.command, timeout: 60 }),
      });
      setRunStatus({ file, result });
    } catch (err) {
      setRunStatus({ file, error: err instanceof Error ? err.message : "Run failed." });
    }
  };

  const runnableFiles = savedFiles.filter((file) => runnerFor(file));

  return (
    <div className="border-t border-gray-800 p-3 space-y-2">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">Output</div>
      {!runId ? (
        <div className="text-xs text-gray-500">Run agents to see the generated code here.</div>
      ) : !report ? (
        <div className="text-xs text-gray-500">Waiting for the agent output...</div>
      ) : (
        <>
          <div className="flex items-center justify-between text-xs">
            <span className="text-gray-400">Result</span>
            <span className={report.verdict === "accepted" ? "text-green-400" : "text-yellow-400"}>
              {report.verdict.replace("_", " ")}
            </span>
          </div>
          {report.files_changed && report.files_changed.length > 0 && (
            <div className="space-y-1">
              <div className="text-[11px] uppercase tracking-wide text-gray-500">Files changed</div>
              {report.files_changed.map((file) => (
                <label key={file} className="flex items-center gap-2 rounded border border-gray-800 bg-black px-2 py-1 text-xs text-gray-200">
                  <input
                    type="checkbox"
                    checked={selectedFiles.includes(file)}
                    onChange={() => toggleFile(file)}
                  />
                  <span>{file}</span>
                </label>
              ))}
            </div>
          )}
          {(!report.files_changed || report.files_changed.length === 0) && (
            <div className="rounded border border-gray-800 bg-black p-2 text-xs text-gray-400">
              No files changed yet. Forge will only show save controls after a model returns a valid diff.
            </div>
          )}
          {report.model_output_errors && report.model_output_errors.length > 0 && (
            <div className="space-y-1 rounded border border-yellow-900 bg-yellow-950/20 p-2 text-xs">
              <div className="text-[11px] uppercase tracking-wide text-yellow-400">Model output diagnostics</div>
              {report.model_output_errors.map((item, index) => (
                <div key={`${item.task ?? "task"}:${index}`} className="text-yellow-100">
                  <div>{item.model ?? "model"}: {item.reason ?? "Invalid output"}</div>
                  {item.preview && <pre className="mt-1 max-h-28 overflow-auto whitespace-pre-wrap text-yellow-200/80">{item.preview}</pre>}
                </div>
              ))}
            </div>
          )}
          {report.requires_save_approval && (
            <div className="space-y-2 rounded border border-yellow-700 bg-black p-2 text-xs">
              <div className="flex justify-between">
                <span className="text-yellow-300">Permission required before save</span>
                <span className="uppercase text-yellow-400">{report.risk_level ?? "low"} risk</span>
              </div>
              <div className="text-gray-400">{report.risk_reasons?.join("; ")}</div>
              <label className="flex items-center gap-2 text-gray-300">
                <input type="checkbox" checked={backup} onChange={(event) => setBackup(event.target.checked)} />
                Create backup before save
              </label>
              <div className="grid grid-cols-2 gap-2">
                <button onClick={approveSave} className="rounded bg-forge-accent px-2 py-1.5 text-white">
                  Approve save
                </button>
                <button onClick={rejectSave} className="rounded border border-gray-700 px-2 py-1.5 text-gray-200">
                  Reject save
                </button>
              </div>
              <button className="w-full rounded border border-gray-700 px-2 py-1.5 text-gray-300" onClick={() => setSaveStatus("Edit manually: copy or adjust the generated patch before approving.")}>
                Edit manually
              </button>
              {saveStatus && <div className="text-gray-300">{saveStatus}</div>}
            </div>
          )}
          {runnableFiles.length > 0 && (
            <div className="space-y-2 rounded border border-cyan-900 bg-cyan-950/20 p-2 text-xs">
              <div className="text-[11px] uppercase tracking-wide text-cyan-300">Run saved code</div>
              <div className="grid gap-2">
                {runnableFiles.map((file) => {
                  const runner = runnerFor(file);
                  return (
                    <button
                      key={file}
                      type="button"
                      className="rounded bg-cyan-500 px-2 py-1.5 font-medium text-black hover:bg-cyan-400"
                      onClick={() => runSavedFile(file)}
                    >
                      {runner?.label}: {file}
                    </button>
                  );
                })}
              </div>
              {runStatus && (
                <div className="rounded border border-gray-800 bg-black p-2">
                  <div className="text-gray-400">{runStatus.file}</div>
                  {runStatus.error && <pre className="mt-1 whitespace-pre-wrap text-red-300">{runStatus.error}</pre>}
                  {runStatus.result && (
                    <>
                      {runStatus.result.stdout && <pre className="mt-1 whitespace-pre-wrap text-gray-100">{runStatus.result.stdout}</pre>}
                      {runStatus.result.stderr && <pre className="mt-1 whitespace-pre-wrap text-amber-300">{runStatus.result.stderr}</pre>}
                      <div className={runStatus.result.exit_code === 0 ? "text-green-400" : "text-red-300"}>
                        exit {runStatus.result.exit_code}
                      </div>
                    </>
                  )}
                  {!runStatus.error && !runStatus.result && <div className="text-gray-500">running...</div>}
                </div>
              )}
            </div>
          )}
          {report.explanation && (
            <div className="rounded border border-gray-800 bg-black p-2 text-xs text-gray-300">
              {report.explanation}
            </div>
          )}
          {report.patches?.map((patch) => (
            <div key={`diff:${patch.file_path}`} className="space-y-1">
              <div className="text-[11px] uppercase tracking-wide text-gray-500">Diff: {patch.file_path}</div>
              <pre className="max-h-64 overflow-auto rounded border border-gray-800 bg-black p-2 text-xs leading-5 text-gray-100">
                <code>{patch.patch}</code>
              </pre>
            </div>
          ))}
          {report.artifacts?.map((artifact) => (
            <div key={artifact.file_path} className="space-y-1">
              <div className="text-[11px] uppercase tracking-wide text-gray-500">{artifact.file_path}</div>
              <pre className="max-h-80 overflow-auto rounded border border-gray-800 bg-black p-2 text-xs leading-5 text-gray-100">
                <code>{artifact.content}{artifact.truncated ? "\n..." : ""}</code>
              </pre>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
