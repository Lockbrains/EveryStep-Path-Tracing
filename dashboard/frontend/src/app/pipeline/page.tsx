"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight } from "lucide-react";
import {
  type PipelineEvent,
  startPipeline,
  streamPipeline,
} from "@/lib/api";

const STEPS = [
  { name: "Worldview", samples: 48, avgQuality: 0.71, status: "complete" },
  { name: "Palette", samples: 36, avgQuality: 0.74, status: "complete" },
  { name: "Materials", samples: 42, avgQuality: 0.69, status: "running" },
  { name: "Characters", samples: 0, avgQuality: 0, status: "pending" },
  { name: "Environments", samples: 0, avgQuality: 0, status: "pending" },
] as const;

function StepCard({
  name,
  samples,
  avgQuality,
  status,
}: {
  name: string;
  samples: number;
  avgQuality: number;
  status: string;
}) {
  return (
    <div className="w-[140px] shrink-0 rounded-xl border border-zinc-800 bg-zinc-900 p-3">
      <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
        Step
      </p>
      <p className="mt-1 text-sm font-semibold text-zinc-100">{name}</p>
      <dl className="mt-3 space-y-1 text-xs text-zinc-400">
        <div className="flex justify-between gap-2">
          <dt>Samples</dt>
          <dd className="tabular-nums text-zinc-300">{samples}</dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Avg Q</dt>
          <dd className="tabular-nums text-zinc-300">
            {avgQuality > 0 ? avgQuality.toFixed(2) : "—"}
          </dd>
        </div>
        <div className="flex justify-between gap-2">
          <dt>Status</dt>
          <dd className="capitalize text-zinc-300">{status}</dd>
        </div>
      </dl>
    </div>
  );
}

export default function PipelinePage() {
  const [log, setLog] = useState<PipelineEvent[]>(() => [
    {
      event_type: "init",
      step: 0,
      data: { message: "Pipeline log — connect the backend to stream live events." },
      timestamp: new Date().toISOString(),
    },
  ]);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => stopRef.current?.();
  }, []);

  const flow = useMemo(
    () =>
      STEPS.map((s, i) => (
        <div key={s.name} className="flex items-center gap-1">
          {i > 0 && (
            <ChevronRight
              className="size-5 shrink-0 text-zinc-600"
              aria-hidden
            />
          )}
          <StepCard {...s} />
        </div>
      )),
    [],
  );

  const attachStream = async () => {
    stopRef.current?.();
    stopRef.current = null;
    try {
      const runId = await startPipeline({});
      const stop = streamPipeline(runId, (ev) =>
        setLog((prev) => [...prev, ev]),
      );
      stopRef.current = stop;
    } catch {
      setLog((prev) => [
        ...prev,
        {
          event_type: "error",
          step: -1,
          data: { message: "Could not open SSE — showing mock entry." },
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  return (
    <div className="flex min-h-full flex-col p-6">
      <div className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
          Agent pipeline
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Five-step Art Bible chain — React Flow DAG placeholder above the log
        </p>
      </div>

      <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900 p-6">
        <p className="mb-4 text-xs font-medium uppercase tracking-wide text-zinc-500">
          React Flow canvas (placeholder)
        </p>
        <div className="flex min-h-[140px] items-center justify-center overflow-x-auto rounded-lg border border-dashed border-zinc-700 bg-zinc-950/50 py-4">
          <div className="flex flex-wrap items-center justify-center gap-1 px-2">
            {flow}
          </div>
        </div>
      </div>

      <div className="flex flex-1 flex-col rounded-xl border border-zinc-800 bg-zinc-900">
        <div className="flex items-center justify-between border-b border-zinc-800 px-4 py-3">
          <h2 className="text-sm font-semibold text-zinc-100">Pipeline log</h2>
          <button
            type="button"
            onClick={attachStream}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            Stream from API
          </button>
        </div>
        <div className="max-h-[320px] flex-1 overflow-y-auto p-4 font-mono text-xs text-zinc-400">
          {log.map((e, i) => (
            <pre
              key={`${e.timestamp}-${i}`}
              className="mb-2 whitespace-pre-wrap break-all border-l-2 border-zinc-700 pl-3"
            >
              {JSON.stringify(e, null, 2)}
            </pre>
          ))}
        </div>
      </div>
    </div>
  );
}
