"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

type Report = {
  verdict: string;
  gates: Record<string, { passed?: boolean; approved?: boolean; confidence?: number; high?: number }>;
  files_changed: string[];
  risky_actions: { kind: string; detail?: string }[];
  pending_approval?: boolean;
};

const GATE_LABELS: [string, string][] = [
  ["tests", "Tests"],
  ["hallucination", "Hallucination check"],
  ["security", "Security"],
  ["static", "Static checks"],
  ["review", "Multi-agent review"],
];

function mark(ok: boolean | undefined) {
  return ok ? "PASS" : "FAIL";
}

export default function VerificationReport({ runId }: { runId: string | null }) {
  const [rep, setRep] = useState<Report | null>(null);

  useEffect(() => {
    if (!runId) return;
    let live = true;
    const load = async () => {
      try {
        const r = await api<Report>(`/api/runs/${runId}/report`);
        if (live) setRep(r);
      } catch {
        /* not ready */
      }
    };
    load();
    const t = setInterval(load, 3000);
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [runId]);

  const approve = async () => {
    if (!runId) return;
    await api(`/api/runs/${runId}/approve`, { method: "POST" });
  };

  const verdict = rep?.verdict ?? "pending";
  const verdictColor =
    verdict === "accepted" ? "text-green-400" : verdict === "awaiting_approval" ? "text-yellow-400" : "text-gray-400";

  return (
    <div className="space-y-2 border-t border-gray-800 p-3">
      <div className="text-[11px] uppercase tracking-wide text-gray-500">Verification report</div>
      {!runId ? (
        <div className="text-xs text-gray-500">Run an agent to see the report.</div>
      ) : (
        <>
          <div className={`text-sm font-semibold ${verdictColor}`}>{verdict.replace("_", " ")}</div>
          <div className="space-y-1">
            {GATE_LABELS.map(([key, label]) => {
              const g = rep?.gates?.[key];
              const ok = key === "review" ? g?.approved : g?.passed;
              const extra =
                key === "hallucination" && g?.confidence != null
                  ? ` (conf ${g.confidence})`
                  : key === "security" && g?.high != null
                    ? ` (${g.high} high)`
                    : "";
              return (
                <div key={key} className="flex justify-between text-xs">
                  <span className="text-gray-300">
                    {label}
                    {extra}
                  </span>
                  <span>{mark(ok)}</span>
                </div>
              );
            })}
          </div>
          {rep?.risky_actions && rep.risky_actions.length > 0 && (
            <div className="space-y-1 pt-1">
              <div className="text-[11px] uppercase tracking-wide text-yellow-500">Risky actions</div>
              {rep.risky_actions.map((a, i) => (
                <div key={i} className="text-xs text-yellow-300">
                  Risk: {a.kind}
                  {a.detail ? `: ${a.detail}` : ""}
                </div>
              ))}
            </div>
          )}
          {rep?.pending_approval && (
            <button onClick={approve} className="w-full rounded bg-yellow-600 py-1.5 text-xs font-medium text-white">
              Approve risky actions
            </button>
          )}
        </>
      )}
    </div>
  );
}
