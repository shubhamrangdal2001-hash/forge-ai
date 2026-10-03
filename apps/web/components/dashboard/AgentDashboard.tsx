"use client";
import { useEffect, useState } from "react";
import { runStreamUrl } from "@/lib/ws";
import { api } from "@/lib/api";
import ModelPicker from "@/components/dashboard/ModelPicker";
import LocalModelManager from "@/components/dashboard/LocalModelManager";
import NvidiaControlPanel from "@/components/dashboard/NvidiaControlPanel";

type Step = { agent_role: string; model: string; status: string; phase: string };
type ComputeRoute = "local" | "nvidia";

const PRO_PROMPT = `Build this in Forge like a senior autonomous engineer. Inspect the workspace first, make the smallest high-quality change, prefer verified diffs, run the relevant tests, and explain exactly what changed. Use the selected route only: local models when Local is selected, NVIDIA API models when NVIDIA API is selected. Aim for a workflow that beats Antigravity, Cursor, and KIMI Work by being grounded, test-first, transparent, and safe.`;

export default function AgentDashboard({ projectId, onRunId }: { projectId: string; onRunId?: (id: string) => void }) {
  const [goal, setGoal] = useState("");
  const [mode, setMode] = useState("nvidia_only");
  const [localOnly, setLocalOnly] = useState(false);
  const [computeRoute, setComputeRoute] = useState<ComputeRoute>("nvidia");
  const [models, setModels] = useState<Record<string, string>>({});
  const [runId, setRunId] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    const ws = new WebSocket(runStreamUrl(runId));
    ws.onmessage = (event) => {
      try {
        const step = JSON.parse(event.data);
        setSteps((prev) => [...prev, step]);
      } catch {}
    };
    return () => ws.close();
  }, [runId]);

  const start = async () => {
    const trimmedGoal = goal.trim();
    if (!trimmedGoal || starting) return;
    setStarting(true);
    setStartError(null);
    try {
      const response = await api<{ id: string }>("/api/runs", {
        method: "POST",
        body: JSON.stringify({
          goal: trimmedGoal,
          project_id: projectId,
          router_mode: mode,
          local_only: localOnly || mode === "offline" || mode === "cpu_only",
          models,
        }),
      });
      setRunId(response.id);
      setSteps([]);
      onRunId?.(response.id);
    } catch (error) {
      setStartError(error instanceof Error ? error.message : "Unable to start the agent run.");
    } finally {
      setStarting(false);
    }
  };

  const applyRoute = (route: ComputeRoute) => {
    setComputeRoute(route);
    if (route === "local") {
      setMode("offline");
      setLocalOnly(true);
      return;
    }
    setMode("nvidia_only");
    setLocalOnly(false);
  };

  const updateMode = (nextMode: string) => {
    setMode(nextMode);
    if (nextMode === "nvidia_only") {
      setComputeRoute("nvidia");
      setLocalOnly(false);
    } else if (nextMode === "offline" || nextMode === "cpu_only") {
      setComputeRoute("local");
      setLocalOnly(true);
    }
  };

  const statusColor = (status: string) =>
    status === "passed" || status === "done"
      ? "text-green-400"
      : status === "failed"
        ? "text-red-400"
        : status === "awaiting"
          ? "text-yellow-400"
        : "text-gray-400";

  const runLabel = computeRoute === "nvidia" ? "Run with NVIDIA" : "Run locally";

  return (
    <div className="space-y-3 p-3">
      <div className="rounded-lg border border-gray-800 bg-[#0b1017] p-3 shadow-sm">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-cyan-300">Agent Mission Control</div>
            <div className="mt-1 text-lg font-semibold text-white">Forge command deck</div>
          </div>
          <div className="rounded border border-emerald-700/70 px-2 py-1 text-[11px] text-emerald-300">
            Verified diffs
          </div>
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            data-testid="route-local-button"
            type="button"
            className={`rounded border px-3 py-2 text-left text-xs ${computeRoute === "local" ? "border-emerald-500 bg-emerald-500/10 text-emerald-200" : "border-gray-700 bg-black text-gray-400 hover:text-gray-200"}`}
            onClick={() => applyRoute("local")}
          >
            <div className="font-medium">Local</div>
            <div className="mt-0.5 text-[11px] text-gray-500">Offline or on-device models</div>
          </button>
          <button
            data-testid="route-nvidia-button"
            type="button"
            className={`rounded border px-3 py-2 text-left text-xs ${computeRoute === "nvidia" ? "border-cyan-500 bg-cyan-500/10 text-cyan-200" : "border-gray-700 bg-black text-gray-400 hover:text-gray-200"}`}
            onClick={() => applyRoute("nvidia")}
          >
            <div className="font-medium">NVIDIA API</div>
            <div className="mt-0.5 text-[11px] text-gray-500">NVIDIA-only routing</div>
          </button>
        </div>
      </div>

      <textarea
        data-testid="mission-goal-input"
        className="w-full rounded border border-gray-700 bg-black p-3 text-xs leading-5 text-gray-100 outline-none placeholder:text-gray-600 focus:border-cyan-500"
        rows={5}
        placeholder="Describe the mission. Example: Create a tested Python EDA script for the Titanic dataset using the selected model route."
        value={goal}
        onChange={(event) => setGoal(event.target.value)}
      />
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          className="rounded border border-gray-700 bg-[#0b1017] px-3 py-2 text-xs font-medium text-gray-200 hover:border-cyan-500 hover:text-white"
          onClick={() => setGoal(PRO_PROMPT)}
        >
          Write pro prompt
        </button>
        <button
          data-testid="entry-mission-button"
          type="button"
          onClick={start}
          disabled={!goal.trim() || starting}
          title="Start agent run"
          className="rounded bg-cyan-500 px-3 py-2 text-xs font-semibold text-black hover:bg-cyan-400 disabled:cursor-not-allowed disabled:bg-gray-700 disabled:text-gray-400"
        >
          {starting ? "Starting..." : runLabel}
        </button>
      </div>
      {startError && (
        <div className="rounded border border-red-900 bg-red-950/40 px-3 py-2 text-xs text-red-200">
          {startError}
        </div>
      )}

      <ModelPicker value={models} onChange={setModels} />
      <NvidiaControlPanel />
      <LocalModelManager mode={mode} />

      <div className="rounded-lg border border-gray-800 bg-[#0b1017] p-3">
        <div className="mb-2 flex items-center justify-between">
          <span className="text-[11px] uppercase tracking-wide text-gray-500">Advanced route</span>
          <span className="text-[11px] text-gray-500">{computeRoute === "nvidia" ? "NVIDIA API model" : "Local model"}</span>
        </div>
        <select
          className="w-full rounded border border-gray-700 bg-black p-2 text-xs text-gray-100"
          value={mode}
          onChange={(event) => updateMode(event.target.value)}
        >
          <option value="fast">Fast</option>
          <option value="balanced">Balanced</option>
          <option value="accuracy">Accurate</option>
          <option value="offline">Offline</option>
          <option value="nvidia_only">NVIDIA-only</option>
          <option value="hybrid">Hybrid</option>
          <option value="cloud_fallback">Cloud fallback</option>
          <option value="cheap">Cheap</option>
          <option value="cloud_expert">Cloud expert</option>
          <option value="low_ram">Low RAM</option>
          <option value="gpu">GPU</option>
          <option value="cpu_only">CPU-only</option>
        </select>
        <label className="mt-2 flex items-center gap-2 text-xs text-gray-400">
          <input type="checkbox" checked={localOnly} onChange={(event) => setLocalOnly(event.target.checked)} className="accent-cyan-500" />
          Local only
        </label>
      </div>

      <div className="space-y-1">
        {steps.map((step, index) => (
          <div key={index} className="rounded border border-gray-800 bg-black/40 p-2 text-xs">
            <div className="flex justify-between">
              <span className="font-medium">{step.agent_role}</span>
              <span className="text-gray-500">{step.model}</span>
            </div>
            <div className={statusColor(step.status)}>{step.phase} - {step.status}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
