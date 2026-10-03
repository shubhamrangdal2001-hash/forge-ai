"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type LocalModel = {
  id: string;
  name: string;
  parameter_size: string;
  best_use_case: string;
  min_ram_gb: number;
  recommended_ram_gb: number;
  min_vram_gb: number;
  recommended_vram_gb: number;
  quantization: string;
  ollama?: string | null;
  product_role: string;
};

type Hardware = {
  ram_gb: number;
  gpu_vram_gb: number;
  tier: { tier: number; name: string };
  ollama_installed: boolean;
  recommendations: LocalModel[];
};

export default function LocalModelManager({ mode }: { mode: string }) {
  const [hardware, setHardware] = useState<Hardware | null>(null);
  const [catalog, setCatalog] = useState<LocalModel[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [message, setMessage] = useState<string>("");

  const load = async () => {
    const [hw, cat] = await Promise.all([
      api<Hardware>(`/api/local-models/hardware?mode=${encodeURIComponent(mode)}`),
      api<{ models: LocalModel[] }>("/api/local-models/catalog"),
    ]);
    setHardware(hw);
    setCatalog(cat.models);
    setSelected((current) => current || hw.recommendations?.[0]?.id || cat.models[0]?.id || "");
  };

  useEffect(() => {
    load().catch(() => setMessage("Local model detection unavailable."));
  }, [mode]);

  const selectedModel = useMemo(() => catalog.find((m) => m.id === selected), [catalog, selected]);

  const stagePull = async () => {
    if (!selected) return;
    const res = await api<{ command?: string; message: string }>("/api/local-models/ollama/pull", {
      method: "POST",
      body: JSON.stringify({ model_id: selected }),
    });
    setMessage(res.command ? `${res.command}` : res.message);
  };

  const benchmark = async () => {
    if (!selected) return;
    const res = await api<{ next_step: string }>("/api/local-models/benchmark", {
      method: "POST",
      body: JSON.stringify({ model_id: selected }),
    });
    setMessage(res.next_step);
  };

  return (
    <div className="space-y-2 rounded border border-gray-800 p-2">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wide text-gray-500">Local models</span>
        <button onClick={load} className="rounded border border-gray-700 px-2 py-0.5 text-[11px] text-gray-300">
          Refresh
        </button>
      </div>
      {hardware && (
        <div className="grid grid-cols-3 gap-1 text-[11px] text-gray-400">
          <div>{hardware.ram_gb} GB RAM</div>
          <div>{hardware.gpu_vram_gb} GB VRAM</div>
          <div>Tier {hardware.tier.tier}</div>
        </div>
      )}
      <select
        className="w-full rounded border border-gray-700 bg-black p-1.5 text-xs"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        {catalog.map((m) => (
          <option key={m.id} value={m.id}>
            {m.name} - {m.parameter_size}
          </option>
        ))}
      </select>
      {selectedModel && (
        <div className="space-y-1 text-[11px] text-gray-400">
          <div>{selectedModel.best_use_case}</div>
          <div>
            RAM {selectedModel.min_ram_gb}/{selectedModel.recommended_ram_gb} GB - VRAM{" "}
            {selectedModel.min_vram_gb}/{selectedModel.recommended_vram_gb} GB - {selectedModel.quantization}
          </div>
        </div>
      )}
      <div className="flex gap-2">
        <button onClick={stagePull} className="flex-1 rounded bg-gray-800 px-2 py-1 text-xs text-gray-200">
          Install cmd
        </button>
        <button onClick={benchmark} className="flex-1 rounded bg-gray-800 px-2 py-1 text-xs text-gray-200">
          Benchmark
        </button>
      </div>
      {hardware?.recommendations?.length ? (
        <div className="space-y-1">
          <div className="text-[11px] uppercase tracking-wide text-gray-500">Recommended</div>
          {hardware.recommendations.slice(0, 3).map((m) => (
            <div key={m.id} className="rounded bg-black p-1.5 text-[11px] text-gray-300">
              {m.name} <span className="text-gray-500">for {m.product_role}</span>
            </div>
          ))}
        </div>
      ) : null}
      {message && <div className="rounded border border-gray-800 bg-black p-1.5 text-[11px] text-gray-400">{message}</div>}
    </div>
  );
}
