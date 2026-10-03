"use client";
import { KeyboardEvent, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type TerminalResult = {
  command: string;
  cwd: string;
  exit_code: number;
  stdout: string;
  stderr: string;
  timed_out: boolean;
};

type Entry =
  | { kind: "banner"; text: string }
  | { kind: "command"; command: string }
  | { kind: "result"; result: TerminalResult }
  | { kind: "error"; text: string };

const QUICK_COMMANDS = [
  { label: "ls", command: "Get-ChildItem -Force" },
  { label: "py", command: "python --version" },
  { label: "git", command: "git status --short" },
];

export default function Terminal({ projectId, projectRoot }: { projectId: string; projectRoot: string }) {
  const [command, setCommand] = useState("");
  const [entries, setEntries] = useState<Entry[]>([
    { kind: "banner", text: "Forge terminal ready. Commands run from the selected project folder." },
  ]);
  const [running, setRunning] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number | null>(null);
  const outputRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    outputRef.current?.scrollTo({ top: outputRef.current.scrollHeight });
  }, [entries, running]);

  const run = async (nextCommand = command) => {
    const trimmed = nextCommand.trim();
    if (!trimmed || running) return;

    setRunning(true);
    setCommand("");
    setHistory((prev) => [trimmed, ...prev.filter((item) => item !== trimmed)].slice(0, 20));
    setHistoryIndex(null);
    setEntries((prev) => [...prev, { kind: "command", command: trimmed }]);

    try {
      const result = await api<TerminalResult>("/api/terminal/run", {
        method: "POST",
        body: JSON.stringify({ project_id: projectId, command: trimmed, timeout: 60 }),
      });
      setEntries((prev) => [...prev, { kind: "result", result }]);
    } catch (error) {
      setEntries((prev) => [
        ...prev,
        { kind: "error", text: error instanceof Error ? error.message : "Command failed." },
      ]);
    } finally {
      setRunning(false);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      run();
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      const next = historyIndex === null ? 0 : Math.min(historyIndex + 1, history.length - 1);
      setHistoryIndex(next);
      setCommand(history[next] ?? command);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (historyIndex === null) return;
      const next = historyIndex - 1;
      setHistoryIndex(next >= 0 ? next : null);
      setCommand(next >= 0 ? history[next] : "");
    }
  };

  return (
    <div className="flex h-full flex-col border-t border-gray-800 bg-[#05070a]">
      <div className="flex items-center justify-between border-b border-gray-800 px-3 py-2">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wide text-cyan-300">Forge Terminal</div>
          <div className="truncate text-[11px] text-gray-500" title={projectRoot}>
            {projectRoot}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {QUICK_COMMANDS.map((item) => (
            <button
              key={item.command}
              type="button"
              className="h-7 min-w-8 rounded border border-gray-700 px-2 text-[11px] text-gray-300 hover:border-cyan-500 hover:text-white"
              title={item.command}
              onClick={() => run(item.command)}
              disabled={running}
            >
              {item.label}
            </button>
          ))}
          <button
            type="button"
            className="h-7 rounded border border-gray-700 px-2 text-[11px] text-gray-400 hover:text-white"
            onClick={() => setEntries([{ kind: "banner", text: "Terminal cleared." }])}
          >
            Clear
          </button>
        </div>
      </div>

      <div ref={outputRef} className="min-h-0 flex-1 overflow-auto px-3 py-2 font-mono text-[12px] leading-5">
        {entries.map((entry, index) => {
          if (entry.kind === "banner") {
            return <div key={index} className="text-gray-500">{entry.text}</div>;
          }
          if (entry.kind === "command") {
            return (
              <div key={index} className="mt-2 text-cyan-300">
                <span className="text-gray-600">forge&gt;</span> {entry.command}
              </div>
            );
          }
          if (entry.kind === "error") {
            return <pre key={index} className="whitespace-pre-wrap text-red-300">{entry.text}</pre>;
          }
          const { result } = entry;
          return (
            <div key={index} className="mb-1">
              {result.stdout && <pre className="whitespace-pre-wrap text-gray-200">{result.stdout}</pre>}
              {result.stderr && <pre className="whitespace-pre-wrap text-amber-300">{result.stderr}</pre>}
              <div className={result.exit_code === 0 ? "text-green-400" : "text-red-300"}>
                exit {result.exit_code}{result.timed_out ? " timeout" : ""}
              </div>
            </div>
          );
        })}
        {running && <div className="mt-2 text-gray-500">running...</div>}
      </div>

      <div className="flex items-center gap-2 border-t border-gray-800 px-3 py-2">
        <span className="font-mono text-xs text-cyan-300">forge&gt;</span>
        <input
          data-testid="forge-terminal-input"
          className="min-w-0 flex-1 bg-transparent font-mono text-xs text-gray-100 outline-none placeholder:text-gray-600"
          placeholder="Run a workspace command"
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={onKeyDown}
          disabled={running}
        />
        <button
          data-testid="forge-terminal-run"
          type="button"
          className="rounded bg-cyan-500 px-3 py-1.5 text-xs font-medium text-black hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-400"
          onClick={() => run()}
          disabled={running || !command.trim()}
        >
          Run
        </button>
      </div>
    </div>
  );
}
