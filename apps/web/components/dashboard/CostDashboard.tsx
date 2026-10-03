"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type ModelCost = { calls: number; tokens: number; cost_usd: number };
type Cost = { total_cost_usd: number; total_tokens: number; calls: number; by_model: Record<string, ModelCost> };

export default function CostDashboard({ runId }: { runId: string | null }) {
  const [cost, setCost] = useState<Cost | null>(null);

  useEffect(() => {
    if (!runId) return;
    let live = true;
    const load = async () => {
      try {
        const c = await api<Cost>(`/api/runs/${runId}/cost`);
        if (live) setCost(c);
      } catch {
        /* run may not have a report yet */
      }
    };
    load();
    const t = setInterval(load, 3000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [runId]);

  const total = cost ? Number(cost.total_cost_usd || 0).toFixed(4) : "0.0000";
  const models = cost ? Object.entries(cost.by_model || {}) : [];

  return (
    <div className="space-y-2 border-t border-gray-800 p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">Cost dashboard</div>
      {!runId ? (
        <div className="text-xs text-gray-500">Start a run to track spend.</div>
      ) : (
        <>
          <div className="text-2xl font-semibold text-forge-accent">${total}</div>
          <div className="text-xs text-gray-400">
            {cost?.calls ?? 0} model calls - {cost?.total_tokens ?? 0} tokens
          </div>
          <div className="space-y-1 pt-1">
            {models.map(([model, v]) => (
              <div key={model} className="flex justify-between gap-2 rounded border border-gray-800 p-2 text-xs">
                <span className="min-w-0 truncate font-medium" title={model}>
                  {model}
                </span>
                <span className="shrink-0 text-gray-400">
                  ${Number(v.cost_usd).toFixed(4)} - {v.calls}x
                </span>
              </div>
            ))}
            {models.length === 0 && <div className="text-xs text-gray-500">No spend recorded yet.</div>}
          </div>
        </>
      )}
    </div>
  );
}
