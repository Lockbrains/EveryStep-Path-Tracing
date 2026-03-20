"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BarChart3, FileText, Zap } from "lucide-react";
import {
  type PipelineEvent,
  startPipeline,
  streamPipeline,
} from "@/lib/api";
import { cn } from "@/lib/utils";

function qualityFromEvent(e: PipelineEvent): number | null {
  const d = e.data;
  if (d && typeof d === "object") {
    const o = d as Record<string, unknown>;
    if (typeof o.bestQuality === "number") return o.bestQuality;
    if (typeof o.quality === "number") return o.quality;
  }
  return null;
}

function CardShell({
  title,
  icon: Icon,
  status,
  children,
  className,
}: {
  title: string;
  icon: typeof Zap;
  status: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900",
        className,
      )}
    >
      <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
        <div className="flex items-center gap-2">
          <Icon className="size-4 text-emerald-500" aria-hidden />
          <h2 className="text-sm font-semibold text-zinc-100">{title}</h2>
        </div>
        <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-0.5 text-xs font-medium text-zinc-300">
          {status}
        </span>
      </div>
      <div className="min-h-[180px] flex-1 p-4">{children}</div>
    </div>
  );
}

export default function DashboardPage() {
  const [running, setRunning] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [currentBestQuality, setCurrentBestQuality] = useState(0);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      stopRef.current?.();
    };
  }, []);

  const handleStartPipeline = useCallback(async () => {
    stopRef.current?.();
    stopRef.current = null;
    setRunning(true);
    setStreaming(false);
    setEvents([]);
    setCurrentBestQuality(0);

    try {
      const runId = await startPipeline({});
      setStreaming(true);
      const stop = streamPipeline(
        runId,
        (ev) => {
          setEvents((prev) => [...prev, ev]);
          const q = qualityFromEvent(ev);
          if (q != null) {
            setCurrentBestQuality((b) => Math.max(b, q));
          }
        },
        () => setStreaming(false),
      );
      stopRef.current = () => {
        stop();
        setStreaming(false);
      };
    } catch {
      const now = new Date().toISOString();
      const mock: PipelineEvent[] = [
        {
          event_type: "placeholder",
          step: 0,
          data: {
            message:
              "Backend unreachable — placeholder stream. Start the API on port 8000 for live data.",
          },
          timestamp: now,
        },
        {
          event_type: "metrics",
          step: 1,
          data: { bestQuality: 0.72, quality: 0.68 },
          timestamp: now,
        },
      ];
      setEvents(mock);
      setCurrentBestQuality(0.72);
    } finally {
      setRunning(false);
    }
  }, []);

  const live = running || streaming || events.length > 0;
  const pathStatus = live ? "Live" : "Ready";
  const bibleStatus = running || streaming ? "Generating" : live ? "Live" : "Ready";
  const metricsStatus = live ? "Live" : "Ready";

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
            Dashboard
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            Path tree, Art Bible preview, and sampling metrics
          </p>
        </div>
        <button
          type="button"
          onClick={handleStartPipeline}
          disabled={running || streaming}
          className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
        >
          {running ? "Starting…" : streaming ? "Streaming…" : "Start Pipeline"}
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <CardShell title="Path Tree" icon={Zap} status={pathStatus}>
          <div className="flex h-full min-h-[160px] items-center justify-center rounded-lg border border-dashed border-zinc-700 bg-zinc-950/50 text-center text-sm text-zinc-500">
            D3 path tree visualization placeholder
          </div>
        </CardShell>
        <CardShell title="Art Bible Preview" icon={FileText} status={bibleStatus}>
          <div className="flex h-full min-h-[160px] items-center justify-center rounded-lg border border-dashed border-zinc-700 bg-zinc-950/50 text-center text-sm text-zinc-500">
            Markdown / section preview placeholder
          </div>
        </CardShell>
        <CardShell
          title="Metrics"
          icon={BarChart3}
          status={metricsStatus}
          className="lg:col-span-2"
        >
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Events
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">
                {events.length}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Best quality
              </p>
              <p className="mt-1 text-2xl font-semibold tabular-nums text-zinc-100">
                {currentBestQuality.toFixed(2)}
              </p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                Charts
              </p>
              <p className="mt-1 text-sm text-zinc-500">
                Recharts placeholders will mount here
              </p>
            </div>
          </div>
        </CardShell>
      </div>
    </div>
  );
}
