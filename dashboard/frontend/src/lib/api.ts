import type { ExperimentConfig } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface PipelineEvent {
  event_type: string;
  step: number;
  data: unknown;
  timestamp: string;
}

export async function apiPost(
  path: string,
  body: unknown,
): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new Error(`POST ${path} failed: ${res.status}`);
  }
  return res.json();
}

export async function apiGet(path: string): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`GET ${path} failed: ${res.status}`);
  }
  return res.json();
}

export function createSSEStream(path: string): EventSource {
  return new EventSource(`${API_BASE}${path}`);
}

function parseRunId(data: unknown): string {
  if (data && typeof data === "object") {
    const o = data as Record<string, unknown>;
    const id = o.run_id ?? o.runId;
    if (typeof id === "string" && id.length > 0) return id;
  }
  throw new Error("No run_id in response");
}

export async function startPipeline(
  config: Record<string, unknown>,
): Promise<string> {
  const data = await apiPost("/api/pipeline/run", config);
  return parseRunId(data);
}

export function streamPipeline(
  runId: string,
  onEvent: (event: PipelineEvent) => void,
  onStreamError?: () => void,
): () => void {
  const es = createSSEStream(`/api/pipeline/stream/${runId}`);
  const handler = (ev: MessageEvent) => {
    try {
      onEvent(JSON.parse(ev.data) as PipelineEvent);
    } catch {
      /* ignore malformed chunks */
    }
  };
  const onError = () => {
    onStreamError?.();
    es.close();
  };
  es.addEventListener("message", handler);
  es.addEventListener("error", onError);
  return () => {
    es.removeEventListener("message", handler);
    es.removeEventListener("error", onError);
    es.close();
  };
}

export async function startExperiment(
  config: ExperimentConfig,
): Promise<string> {
  const data = await apiPost("/api/experiment/run", config);
  return parseRunId(data);
}

export function streamExperiment(
  runId: string,
  onEvent: (event: PipelineEvent) => void,
  onStreamError?: () => void,
): () => void {
  const es = createSSEStream(`/api/experiment/stream/${runId}`);
  const handler = (ev: MessageEvent) => {
    try {
      onEvent(JSON.parse(ev.data) as PipelineEvent);
    } catch {
      /* ignore malformed chunks */
    }
  };
  const onError = () => {
    onStreamError?.();
    es.close();
  };
  es.addEventListener("message", handler);
  es.addEventListener("error", onError);
  return () => {
    es.removeEventListener("message", handler);
    es.removeEventListener("error", onError);
    es.close();
  };
}
