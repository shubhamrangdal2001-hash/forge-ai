"use client";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

type NvidiaSettings = {
  provider_enabled: boolean;
  connection_status: string;
  default_model?: string | null;
  provider_priority: string[];
  streaming_enabled: boolean;
  context_limit?: number | null;
  require_file_upload_approval: boolean;
  excluded_folders: string[];
};

type NvidiaStatus = {
  configured: boolean;
  provider_enabled: boolean;
  connection_status: string;
  api_key_source: string;
  api_key_hint?: string | null;
  model_count: number;
  last_refresh_at?: string | null;
  last_validation_at?: string | null;
  last_error?: string | null;
  settings: NvidiaSettings;
  token_usage: { total_tokens: number; requests: number; by_model: Record<string, number> };
  request_history: Array<{ at: string; kind: string; model: string; total_tokens: number }>;
};

type NvidiaModel = {
  id: string;
  display_name: string;
  model_name: string;
  model_provider?: string | null;
  parameter_size?: string | null;
  context_window?: number | null;
  max_output_tokens?: number | null;
  capabilities: string[];
  supported_languages: string[];
  coding_capability: string;
  reasoning_capability: string;
  vision_support: boolean;
  embedding_support: boolean;
  chat_capability: boolean;
  function_calling_support: boolean;
  structured_output_support: boolean;
  recommended_use_cases: string[];
  relative_latency: string;
  relative_quality: string;
  relative_cost: string;
  current_availability: string;
  favorite: boolean;
  is_default: boolean;
};

const priorityPresets = [
  { id: "local,nvidia,secondary_cloud,user_fallback", label: "Hybrid fallback" },
  { id: "nvidia,local,secondary_cloud,user_fallback", label: "NVIDIA first" },
  { id: "nvidia", label: "NVIDIA only" },
  { id: "local", label: "Local only" },
];

const qualityRank: Record<string, number> = {
  frontier: 5,
  very_high: 5,
  high: 4,
  medium_high: 4,
  medium: 3,
  low: 2,
  unknown: 1,
};

const latencyRank: Record<string, number> = {
  very_low: 5,
  low: 4,
  medium: 3,
  balanced: 3,
  high: 2,
  very_high: 1,
  unknown: 0,
};

function compactNumber(value?: number | null) {
  if (!value) return "-";
  if (value >= 1_000_000) return `${Math.round(value / 1_000_000)}M`;
  if (value >= 1_000) return `${Math.round(value / 1_000)}K`;
  return `${value}`;
}

function statusColor(status: string) {
  if (status === "connected" || status === "available") return "text-green-400";
  if (status === "invalid" || status === "failed") return "text-red-400";
  if (status === "degraded") return "text-yellow-400";
  return "text-gray-400";
}

export default function NvidiaControlPanel() {
  const [tab, setTab] = useState<"settings" | "models">("settings");
  const [status, setStatus] = useState<NvidiaStatus | null>(null);
  const [models, setModels] = useState<NvidiaModel[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [query, setQuery] = useState("");
  const [capability, setCapability] = useState("all");
  const [sort, setSort] = useState("quality");
  const [compare, setCompare] = useState<string[]>([]);
  const [benchmark, setBenchmark] = useState<Record<string, string>>({});

  const loadStatus = async () => {
    const data = await api<NvidiaStatus>("/api/nvidia/status");
    setStatus(data);
  };

  const loadModels = async (refresh = false) => {
    const data = await api<{ models: NvidiaModel[] }>(refresh ? "/api/nvidia/models/refresh" : "/api/nvidia/models", {
      method: refresh ? "POST" : "GET",
    });
    setModels(data.models);
  };

  useEffect(() => {
    Promise.all([loadStatus(), loadModels(false)]).catch((err) => setMessage(err.message));
  }, []);

  const settings = status?.settings;
  const priorityValue = settings?.provider_priority?.join(",") ?? priorityPresets[0].id;

  const saveKey = async () => {
    setMessage("Validating NVIDIA API key...");
    try {
      const result = await api<{ model_count: number }>("/api/nvidia/api-key", {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey }),
      });
      setApiKey("");
      setMessage(`Connected. ${result.model_count} models discovered.`);
      await Promise.all([loadStatus(), loadModels(false)]);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Validation failed.");
    }
  };

  const validateCurrentKey = async () => {
    setMessage("Checking connection...");
    try {
      await api("/api/nvidia/validate", { method: "POST" });
      setMessage("Connection validated.");
      await loadStatus();
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Validation failed.");
    }
  };

  const removeKey = async () => {
    await api("/api/nvidia/api-key", { method: "DELETE" });
    setMessage("NVIDIA key removed from local storage.");
    await Promise.all([loadStatus(), loadModels(false)]);
  };

  const patchSettings = async (patch: Partial<NvidiaSettings>) => {
    const next = await api<NvidiaSettings>("/api/nvidia/settings", {
      method: "PATCH",
      body: JSON.stringify(patch),
    });
    setStatus((current) => (current ? { ...current, settings: next, provider_enabled: next.provider_enabled, connection_status: next.connection_status } : current));
  };

  const setFavorite = async (model_id: string, favorite: boolean) => {
    await api("/api/nvidia/models/favorite", {
      method: "POST",
      body: JSON.stringify({ model_id, favorite }),
    });
    await Promise.all([loadStatus(), loadModels(false)]);
  };

  const setDefault = async (model_id: string | null) => {
    await api("/api/nvidia/models/default", {
      method: "POST",
      body: JSON.stringify({ model_id }),
    });
    await Promise.all([loadStatus(), loadModels(false)]);
  };

  const runBenchmark = async (model_id: string) => {
    setBenchmark((current) => ({ ...current, [model_id]: "running" }));
    const result = await api<{ status: string; tokens_per_second?: number; error?: string }>("/api/nvidia/benchmark", {
      method: "POST",
      body: JSON.stringify({ model_id }),
    });
    setBenchmark((current) => ({
      ...current,
      [model_id]: result.status === "completed" ? `${result.tokens_per_second ?? "-"} tok/s` : result.error ?? "failed",
    }));
  };

  const refresh = async () => {
    setMessage("Refreshing NVIDIA model catalog...");
    try {
      await loadModels(true);
      await loadStatus();
      setMessage("NVIDIA model catalog refreshed.");
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Refresh failed.");
    }
  };

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = models.filter((m) => {
      const haystack = `${m.display_name} ${m.model_name} ${m.capabilities.join(" ")}`.toLowerCase();
      const matchesQuery = !q || haystack.includes(q);
      const matchesCapability =
        capability === "all" ||
        m.capabilities.includes(capability) ||
        (capability === "vision" && m.vision_support) ||
        (capability === "embedding" && m.embedding_support) ||
        (capability === "tool_calling" && m.function_calling_support) ||
        (capability === "structured_output" && m.structured_output_support);
      return matchesQuery && matchesCapability;
    });
    return [...list].sort((a, b) => {
      if (sort === "latency") return (latencyRank[b.relative_latency] ?? 0) - (latencyRank[a.relative_latency] ?? 0);
      if (sort === "context") return (b.context_window ?? 0) - (a.context_window ?? 0);
      if (sort === "name") return a.display_name.localeCompare(b.display_name);
      return (qualityRank[b.relative_quality] ?? 0) - (qualityRank[a.relative_quality] ?? 0);
    });
  }, [models, query, capability, sort]);

  const comparedModels = compare.map((id) => models.find((m) => m.id === id)).filter(Boolean) as NvidiaModel[];

  return (
    <div className="space-y-2 border-y border-gray-800 py-3">
      <div className="flex items-center justify-between px-3">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-gray-500">NVIDIA AI</div>
          <div className={`text-[11px] ${statusColor(status?.connection_status ?? "not_configured")}`}>
            {status?.connection_status ?? "not_configured"} {status?.model_count ? `- ${status.model_count} models` : ""}
          </div>
        </div>
        <div className="flex rounded border border-gray-800 text-[11px]">
          <button
            className={`px-2 py-1 ${tab === "settings" ? "bg-gray-800 text-gray-100" : "text-gray-400"}`}
            onClick={() => setTab("settings")}
          >
            Settings
          </button>
          <button
            className={`px-2 py-1 ${tab === "models" ? "bg-gray-800 text-gray-100" : "text-gray-400"}`}
            onClick={() => setTab("models")}
          >
            Models
          </button>
        </div>
      </div>

      {tab === "settings" && settings && (
        <div className="space-y-2 px-3 text-xs">
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <input
              type="password"
              className="rounded border border-gray-700 bg-black p-1.5"
              placeholder={status?.api_key_hint ? `Stored ${status.api_key_hint}` : "NVIDIA API key"}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
            <button onClick={saveKey} disabled={!apiKey.trim()} className="rounded bg-forge-accent px-2 py-1 text-white disabled:bg-gray-800">
              Save
            </button>
          </div>
          <div className="flex gap-2">
            <button onClick={validateCurrentKey} className="flex-1 rounded border border-gray-700 px-2 py-1 text-gray-300">
              Validate
            </button>
            <button onClick={removeKey} className="flex-1 rounded border border-gray-700 px-2 py-1 text-gray-300">
              Remove
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <label className="space-y-1">
              <span className="text-[11px] text-gray-500">Default</span>
              <select
                className="w-full rounded border border-gray-700 bg-black p-1.5"
                value={settings.default_model ?? ""}
                onChange={(e) => setDefault(e.target.value || null)}
              >
                <option value="">Smart default</option>
                {models.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[11px] text-gray-500">Priority</span>
              <select
                className="w-full rounded border border-gray-700 bg-black p-1.5"
                value={priorityValue}
                onChange={(e) => patchSettings({ provider_priority: e.target.value.split(",") })}
              >
                {priorityPresets.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="grid grid-cols-2 gap-2 text-[11px] text-gray-400">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={settings.streaming_enabled}
                onChange={(e) => patchSettings({ streaming_enabled: e.target.checked })}
              />
              Streaming
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={settings.require_file_upload_approval}
                onChange={(e) => patchSettings({ require_file_upload_approval: e.target.checked })}
              />
              Upload approval
            </label>
          </div>
          <div className="grid grid-cols-[110px_1fr] gap-2">
            <input
              type="number"
              min={0}
              className="rounded border border-gray-700 bg-black p-1.5"
              placeholder="Context"
              value={settings.context_limit ?? ""}
              onChange={(e) => patchSettings({ context_limit: e.target.value ? Number(e.target.value) : null })}
            />
            <input
              className="rounded border border-gray-700 bg-black p-1.5"
              value={settings.excluded_folders.join(", ")}
              onChange={(e) => patchSettings({ excluded_folders: e.target.value.split(",").map((item) => item.trim()).filter(Boolean) })}
            />
          </div>
          <div className="grid grid-cols-3 gap-1 text-[11px] text-gray-400">
            <div className="rounded bg-black p-1.5">Tokens {status?.token_usage.total_tokens ?? 0}</div>
            <div className="rounded bg-black p-1.5">Requests {status?.token_usage.requests ?? 0}</div>
            <div className="rounded bg-black p-1.5">{status?.api_key_source ?? "none"}</div>
          </div>
          {status?.request_history.length ? (
            <div className="max-h-24 space-y-1 overflow-auto">
              {status.request_history.slice(0, 4).map((row, index) => (
                <div key={`${row.at}-${index}`} className="rounded bg-black p-1.5 text-[11px] text-gray-400">
                  {row.kind} - {row.model} - {row.total_tokens || 0} tokens
                </div>
              ))}
            </div>
          ) : null}
          {status?.last_error && <div className="rounded border border-red-900 bg-black p-1.5 text-[11px] text-red-300">{status.last_error}</div>}
        </div>
      )}

      {tab === "models" && (
        <div className="space-y-2 px-3 text-xs">
          <div className="grid grid-cols-[1fr_auto] gap-2">
            <input className="rounded border border-gray-700 bg-black p-1.5" placeholder="Search models" value={query} onChange={(e) => setQuery(e.target.value)} />
            <button onClick={refresh} className="rounded border border-gray-700 px-2 py-1 text-gray-300">
              Refresh
            </button>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <select className="rounded border border-gray-700 bg-black p-1.5" value={capability} onChange={(e) => setCapability(e.target.value)}>
              <option value="all">All capabilities</option>
              <option value="coding">Coding</option>
              <option value="reasoning">Reasoning</option>
              <option value="vision">Vision</option>
              <option value="embedding">Embeddings</option>
              <option value="chat">Chat</option>
              <option value="tool_calling">Tool calling</option>
              <option value="structured_output">Structured output</option>
            </select>
            <select className="rounded border border-gray-700 bg-black p-1.5" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="quality">Quality</option>
              <option value="latency">Latency</option>
              <option value="context">Context</option>
              <option value="name">Name</option>
            </select>
          </div>
          <div className="max-h-80 space-y-2 overflow-auto pr-1">
            {filtered.map((model) => (
              <div key={model.id} className="rounded border border-gray-800 bg-black p-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-xs font-medium text-gray-100" title={model.model_name}>
                      {model.display_name}
                    </div>
                    <div className="text-[11px] text-gray-500">
                      {model.parameter_size ?? "params -"} - ctx {compactNumber(model.context_window)} - out {compactNumber(model.max_output_tokens)}
                    </div>
                  </div>
                  <div className={`shrink-0 text-[11px] ${statusColor(model.current_availability)}`}>{model.current_availability}</div>
                </div>
                <div className="mt-2 flex flex-wrap gap-1">
                  {model.capabilities.slice(0, 5).map((tag) => (
                    <span key={tag} className="rounded bg-gray-900 px-1.5 py-0.5 text-[10px] text-gray-400">
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="mt-2 grid grid-cols-3 gap-1 text-[11px] text-gray-400">
                  <div>Latency {model.relative_latency}</div>
                  <div>Quality {model.relative_quality}</div>
                  <div>Cost {model.relative_cost}</div>
                </div>
                <div className="mt-2 flex gap-1">
                  <button onClick={() => setFavorite(model.id, !model.favorite)} className="rounded border border-gray-700 px-2 py-1 text-[11px] text-gray-300">
                    {model.favorite ? "Unstar" : "Star"}
                  </button>
                  <button onClick={() => setDefault(model.id)} className="rounded border border-gray-700 px-2 py-1 text-[11px] text-gray-300">
                    {model.is_default ? "Default" : "Pin"}
                  </button>
                  <button onClick={() => runBenchmark(model.id)} className="rounded border border-gray-700 px-2 py-1 text-[11px] text-gray-300">
                    Bench
                  </button>
                  <label className="ml-auto flex items-center gap-1 text-[11px] text-gray-400">
                    <input
                      type="checkbox"
                      checked={compare.includes(model.id)}
                      onChange={(e) =>
                        setCompare((current) =>
                          e.target.checked ? [...current, model.id].slice(-4) : current.filter((id) => id !== model.id),
                        )
                      }
                    />
                    Compare
                  </label>
                </div>
                {benchmark[model.id] && <div className="mt-1 text-[11px] text-gray-500">{benchmark[model.id]}</div>}
              </div>
            ))}
            {!filtered.length && <div className="rounded border border-gray-800 bg-black p-2 text-[11px] text-gray-500">No NVIDIA models cached.</div>}
          </div>
          {comparedModels.length > 1 && (
            <div className="grid grid-cols-2 gap-2">
              {comparedModels.map((model) => (
                <div key={model.id} className="rounded border border-gray-800 bg-black p-2 text-[11px] text-gray-400">
                  <div className="truncate font-medium text-gray-200">{model.display_name}</div>
                  <div>Context {compactNumber(model.context_window)}</div>
                  <div>Quality {model.relative_quality}</div>
                  <div>Latency {model.relative_latency}</div>
                  <div>{model.recommended_use_cases.slice(0, 2).join(", ") || "general"}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {message && <div className="mx-3 rounded border border-gray-800 bg-black p-1.5 text-[11px] text-gray-400">{message}</div>}
    </div>
  );
}
