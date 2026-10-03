function wsBase() {
  if (process.env.NEXT_PUBLIC_WS_BASE) return process.env.NEXT_PUBLIC_WS_BASE;
  if (typeof window === "undefined") return "";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  if (process.env.NODE_ENV === "development") return `${protocol}//${window.location.hostname}:8000`;
  return `${protocol}//${window.location.host}`;
}

export const runStreamUrl = (runId: string) => `${wsBase()}/ws/runs/${runId}`;
