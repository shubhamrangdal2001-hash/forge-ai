"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

export type ModelInfo = {
  id: string;
  label: string;
  provider: string;
  provider_label: string;
  tier: string;
  speed: number;
  accuracy: number;
  price: number;
  context: number;
  tags: string[];
  configured: boolean;
  capabilities?: string[];
  availability_status?: string | null;
  model_name?: string;
  parameter_size?: string | null;
  relative_latency?: string | null;
  relative_quality?: string | null;
};

type Role = { task: string; label: string };
type Catalog = { models: ModelInfo[]; roles: Role[] };

export default function ModelPicker({
  value,
  onChange,
}: {
  value: Record<string, string>;
  onChange: (v: Record<string, string>) => void;
}) {
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [perRole, setPerRole] = useState(false);

  useEffect(() => {
    api<Catalog>("/api/models").then(setCatalog).catch(() => setCatalog(null));
  }, []);

  const grouped = useMemo(() => {
    const groups: Record<string, ModelInfo[]> = {};
    for (const model of catalog?.models ?? []) {
      (groups[model.provider_label] ||= []).push(model);
    }
    return groups;
  }, [catalog]);

  const nvidiaModels = useMemo(
    () =>
      (catalog?.models ?? [])
        .filter((model) => model.provider === "nvidia")
        .sort((a, b) => {
          const quality = (b.accuracy ?? 0) - (a.accuracy ?? 0);
          if (quality) return quality;
          const speed = (b.speed ?? 0) - (a.speed ?? 0);
          if (speed) return speed;
          return a.label.localeCompare(b.label);
        }),
    [catalog],
  );

  const activeNvidiaModel = value.all && nvidiaModels.some((model) => model.id === value.all) ? value.all : "";

  const options = (
    <>
      <option value="">Smart default</option>
      {Object.entries(grouped).map(([provider, models]) => (
        <optgroup key={provider} label={provider}>
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.label}
              {model.tier === "local" ? " - local" : model.provider === "nvidia" ? ` - ctx ${model.context || "?"}` : ` - $${model.price}/M`}
              {model.configured ? "" : " - no key"}
              {model.availability_status ? ` - ${model.availability_status}` : ""}
            </option>
          ))}
        </optgroup>
      ))}
    </>
  );

  const setAll = (id: string) => onChange(id ? { all: id } : {});
  const setRole = (task: string, id: string) => {
    const next = { ...value };
    delete next.all;
    if (id) next[task] = id;
    else delete next[task];
    onChange(next);
  };

  return (
    <div className="space-y-2 rounded-lg border border-gray-800 bg-[#0b1017] p-3">
      <div className="flex items-center justify-between">
        <span className="text-[11px] uppercase tracking-wide text-gray-500">Model routing</span>
        <label className="flex items-center gap-1 text-[11px] text-gray-400">
          <input type="checkbox" checked={perRole} onChange={(event) => setPerRole(event.target.checked)} className="accent-cyan-500" />
          Per role
        </label>
      </div>

      {!perRole && (
        <label className="block space-y-1">
          <span className="text-[11px] text-gray-500">NVIDIA API model</span>
          <select
            data-testid="nvidia-model-select"
            className="w-full rounded border border-gray-700 bg-black p-2 text-xs text-gray-100"
            value={activeNvidiaModel}
            onChange={(event) => setAll(event.target.value)}
          >
            <option value="">Choose from {nvidiaModels.length || 0} NVIDIA models</option>
            {nvidiaModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.label}
                {model.parameter_size ? ` - ${model.parameter_size}` : ""}
                {model.relative_quality ? ` - ${model.relative_quality}` : ""}
                {model.availability_status ? ` - ${model.availability_status}` : ""}
              </option>
            ))}
          </select>
        </label>
      )}

      {!perRole ? (
        <label className="block space-y-1">
          <span className="text-[11px] text-gray-500">Global model override</span>
          <select
            data-testid="all-model-select"
            className="w-full rounded border border-gray-700 bg-black p-2 text-xs text-gray-100"
            value={value.all ?? ""}
            onChange={(event) => setAll(event.target.value)}
          >
            {options}
          </select>
        </label>
      ) : (
        <div className="space-y-1">
          {(catalog?.roles ?? []).map((role) => (
            <div key={role.task} className="flex items-center gap-2">
              <span className="w-24 shrink-0 text-[11px] text-gray-400">{role.label}</span>
              <select
                className="flex-1 rounded border border-gray-700 bg-black p-1.5 text-xs text-gray-100"
                value={value[role.task] ?? ""}
                onChange={(event) => setRole(role.task, event.target.value)}
              >
                {options}
              </select>
            </div>
          ))}
        </div>
      )}
      {!catalog && <div className="text-[11px] text-gray-600">Loading model catalog...</div>}
    </div>
  );
}
