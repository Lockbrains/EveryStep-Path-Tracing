import type { PipelineConfig } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface KeyStatus {
  openai: boolean;
  anthropic: boolean;
  google: boolean;
}

export async function fetchKeyStatus(): Promise<KeyStatus> {
  const res = await fetch(`${API_BASE}/api/keys/status`);
  if (!res.ok) throw new Error(`Key status check failed: ${res.status}`);
  return res.json() as Promise<KeyStatus>;
}

export async function setApiKeys(keys: {
  openai?: string;
  anthropic?: string;
  google?: string;
}): Promise<KeyStatus> {
  const res = await fetch(`${API_BASE}/api/keys`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(keys),
  });
  if (!res.ok) throw new Error(`Set keys failed: ${res.status}`);
  return res.json() as Promise<KeyStatus>;
}

export interface PipelineEvent {
  event_type: string;
  step: number;
  data: Record<string, unknown>;
  timestamp: string;
}

export interface UploadedImage {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
}

export async function uploadImage(file: File): Promise<UploadedImage> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/images/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Upload failed: ${text}`);
  }
  return res.json() as Promise<UploadedImage>;
}

export async function deleteImage(id: string): Promise<void> {
  await fetch(`${API_BASE}/api/images/${id}`, { method: "DELETE" });
}

export function imageUrl(id: string): string {
  return `${API_BASE}/api/images/${id}`;
}

export async function startPipeline(config: PipelineConfig): Promise<string> {
  const res = await fetch(`${API_BASE}/api/pipeline/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(`Pipeline start failed: ${res.status}`);
  const body = (await res.json()) as { run_id: string };
  return body.run_id;
}

export function streamPipeline(
  runId: string,
  onEvent: (event: PipelineEvent) => void,
  onDone?: () => void,
  onError?: () => void,
): () => void {
  const es = new EventSource(`${API_BASE}/api/pipeline/stream/${runId}`);
  es.onmessage = (msg) => {
    try {
      const ev = JSON.parse(msg.data) as PipelineEvent;
      if (ev.event_type === "done") {
        onDone?.();
        es.close();
        return;
      }
      onEvent(ev);
    } catch {
      /* skip malformed */
    }
  };
  es.onerror = () => {
    onError?.();
    es.close();
  };
  return () => es.close();
}
