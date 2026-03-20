"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  type PipelineEvent,
  startExperiment,
  streamExperiment,
} from "@/lib/api";
import type { ExperimentConfig } from "@/lib/types";

const EXPERIMENTS = [
  { id: 0, name: "Point Light Validation" },
  { id: 1, name: "Basic Monte Carlo" },
  { id: 2, name: "Russian Roulette Pruning" },
  { id: 3, name: "Importance Sampling" },
  { id: 4, name: "MLT Mutation" },
  { id: 5, name: "MIS Multi-Strategy" },
  { id: 6, name: "Sampling Efficiency" },
] as const;

const MODEL_OPTIONS = [
  "gpt-4o-mini",
  "claude-haiku",
  "gemini-flash",
  "gpt-4o",
  "claude-sonnet",
  "gemini-pro",
] as const;

export default function ExperimentPage() {
  const [selectedId, setSelectedId] = useState<number | null>(0);
  const [models, setModels] = useState<Set<string>>(
    () => new Set(["gpt-4o-mini"]),
  );
  const [nSamples, setNSamples] = useState(32);
  const [budget, setBudget] = useState("5");
  const [running, setRunning] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [results, setResults] = useState<PipelineEvent[]>([]);
  const stopRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    return () => {
      stopRef.current?.();
    };
  }, []);

  const selected = useMemo(
    () => EXPERIMENTS.find((e) => e.id === selectedId) ?? null,
    [selectedId],
  );

  const toggleModel = (m: string) => {
    setModels((prev) => {
      const next = new Set(prev);
      if (next.has(m)) next.delete(m);
      else next.add(m);
      return next;
    });
  };

  const runExperiment = useCallback(async () => {
    if (selectedId == null || !selected) return;
    stopRef.current?.();
    stopRef.current = null;
    setRunning(true);
    setStreaming(false);
    setResults([]);
    const config: ExperimentConfig = {
      experimentId: selectedId,
      name: selected.name,
      task: "art_bible",
      models: Array.from(models),
      nSamples: [nSamples],
      strategies: ["free", "rag", "tool"],
      budget: budget ? Number(budget) : undefined,
    };
    try {
      const runId = await startExperiment(config);
      setStreaming(true);
      const stop = streamExperiment(
        runId,
        (ev) => setResults((prev) => [...prev, ev]),
        () => setStreaming(false),
      );
      stopRef.current = () => {
        stop();
        setStreaming(false);
      };
    } catch {
      setResults([
        {
          event_type: "mock",
          step: selectedId,
          data: {
            experiment: selected.name,
            note: "Backend offline — placeholder result row.",
            nSamples,
            models: Array.from(models),
          },
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setRunning(false);
    }
  }, [selected, selectedId, models, nSamples, budget]);

  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
        Experiments
      </h1>
      <p className="mt-1 text-sm text-zinc-500">
        Paper experiments 0–6 — configure models, samples, and budget
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-zinc-300">
            Experiment selector
          </h2>
          <ul className="space-y-2">
            {EXPERIMENTS.map((exp) => {
              const active = selectedId === exp.id;
              return (
                <li key={exp.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(exp.id)}
                    className={`w-full rounded-xl border px-4 py-3 text-left transition-colors ${
                      active
                        ? "border-emerald-600/50 bg-zinc-800"
                        : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
                    }`}
                  >
                    <span className="text-xs font-medium text-zinc-500">
                      Exp {exp.id}
                    </span>
                    <p className="mt-0.5 text-sm font-medium text-zinc-100">
                      {exp.name}
                    </p>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
          <h2 className="text-sm font-semibold text-zinc-300">Configuration</h2>
          {!selected ? (
            <p className="mt-4 text-sm text-zinc-500">
              Select an experiment to configure.
            </p>
          ) : (
            <div className="mt-4 space-y-5">
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">
                  Models
                </p>
                <div className="mt-2 flex flex-col gap-2">
                  {MODEL_OPTIONS.map((m) => (
                    <label
                      key={m}
                      className="flex cursor-pointer items-center gap-2 text-sm text-zinc-300"
                    >
                      <input
                        type="checkbox"
                        checked={models.has(m)}
                        onChange={() => toggleModel(m)}
                        className="rounded border-zinc-600 bg-zinc-950 text-emerald-600 focus:ring-emerald-500"
                      />
                      {m}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label
                  htmlFor="n-samples"
                  className="text-xs font-medium uppercase tracking-wide text-zinc-500"
                >
                  N samples ({nSamples})
                </label>
                <input
                  id="n-samples"
                  type="range"
                  min={1}
                  max={256}
                  value={nSamples}
                  onChange={(e) => setNSamples(Number(e.target.value))}
                  className="mt-2 w-full accent-emerald-600"
                />
              </div>
              <div>
                <label
                  htmlFor="budget"
                  className="text-xs font-medium uppercase tracking-wide text-zinc-500"
                >
                  Budget (USD)
                </label>
                <input
                  id="budget"
                  type="number"
                  min={0}
                  step={0.5}
                  value={budget}
                  onChange={(e) => setBudget(e.target.value)}
                  className="mt-2 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-600"
                />
              </div>
              <button
                type="button"
                onClick={runExperiment}
                disabled={running || streaming}
                className="w-full rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
              >
                {running
                  ? "Starting…"
                  : streaming
                    ? "Streaming…"
                    : "Run Experiment"}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-900 p-5">
        <h2 className="text-sm font-semibold text-zinc-300">Results</h2>
        <p className="mt-1 text-xs text-zinc-500">
          Recharts visualizations will render here from experiment metrics.
        </p>
        <div className="mt-4 flex min-h-[200px] items-center justify-center rounded-lg border border-dashed border-zinc-700 bg-zinc-950/50 text-sm text-zinc-500">
          Chart placeholder
        </div>
        {results.length > 0 && (
          <pre className="mt-4 max-h-48 overflow-auto rounded-lg border border-zinc-800 bg-zinc-950 p-3 font-mono text-xs text-zinc-400">
            {JSON.stringify(results, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
