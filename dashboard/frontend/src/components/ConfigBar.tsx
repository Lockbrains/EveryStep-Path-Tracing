"use client";

import { useState } from "react";
import { Play, Square } from "lucide-react";
import type { PipelineConfig, RunStatus, Strategy } from "@/lib/types";
import type { UploadedImage } from "@/lib/api";
import { ImageUpload } from "./ImageUpload";

const STRATEGIES: { value: Strategy; label: string; desc: string }[] = [
  { value: "naive", label: "Naive", desc: "Pure random sampling" },
  { value: "importance", label: "Importance", desc: "Feedback-guided sampling" },
  { value: "mis", label: "MIS", desc: "Free + reference + guided strategies" },
  { value: "nee", label: "NEE", desc: "Reference-grounded generation" },
];

export function ConfigBar({
  runStatus,
  onRun,
  onStop,
}: {
  runStatus: RunStatus;
  onRun: (config: PipelineConfig) => void;
  onStop: () => void;
}) {
  const [brief, setBrief] = useState(
    "A cyberpunk noir game set in a rain-soaked megacity with neon lights and corporate dystopia",
  );
  const [references, setReferences] = useState("");
  const [refImages, setRefImages] = useState<UploadedImage[]>([]);
  const [strategy, setStrategy] = useState<Strategy>("naive");
  const [nSamples, setNSamples] = useState(2);
  const [rrThreshold, setRrThreshold] = useState(0.4);
  const [useMlt, setUseMlt] = useState(false);
  const [mltIter, setMltIter] = useState(10);

  const busy = runStatus === "running";

  const handleRun = () => {
    if (busy) return;
    const refs = references
      .split("\n---\n")
      .map((r) => r.trim())
      .filter(Boolean);
    onRun({
      brief,
      references: refs,
      image_refs: refImages.map((img) => img.id),
      n_samples: nSamples,
      strategies: [strategy],
      rr_threshold: rrThreshold,
      use_mlt: useMlt,
      mlt_iterations: mltIter,
    });
  };

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900 p-5">
      {/* Brief + Text References */}
      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <div>
          <label htmlFor="brief" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Creative Brief
          </label>
          <textarea
            id="brief"
            rows={2}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
            disabled={busy}
            className="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-emerald-600 disabled:opacity-50"
            placeholder="Describe the art direction for your project..."
          />
        </div>
        <div>
          <label htmlFor="refs" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Text References <span className="normal-case text-zinc-600">— separate with ---</span>
          </label>
          <textarea
            id="refs"
            rows={2}
            value={references}
            onChange={(e) => setReferences(e.target.value)}
            disabled={busy}
            className="w-full resize-none rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-indigo-600 disabled:opacity-50"
            placeholder="Paste reference text... separate multiple with a line of ---"
          />
        </div>
      </div>

      {/* Image References */}
      <div className="mb-4">
        <ImageUpload
          images={refImages}
          onChange={setRefImages}
          disabled={busy}
        />
      </div>

      {/* Strategy / Params */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <div>
          <label htmlFor="strategy" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Strategy
          </label>
          <select
            id="strategy"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as Strategy)}
            disabled={busy}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 outline-none focus:border-emerald-600 disabled:opacity-50"
          >
            {STRATEGIES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          <p className="mt-1 text-[10px] text-zinc-600">
            {STRATEGIES.find((s) => s.value === strategy)?.desc}
          </p>
        </div>

        <div>
          <label htmlFor="n-samples" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Samples: {nSamples}
          </label>
          <input
            id="n-samples"
            type="range"
            min={1}
            max={8}
            value={nSamples}
            onChange={(e) => setNSamples(Number(e.target.value))}
            disabled={busy}
            className="mt-2 w-full accent-emerald-600"
          />
        </div>

        <div>
          <label htmlFor="rr" className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            RR Threshold: {rrThreshold.toFixed(2)}
          </label>
          <input
            id="rr"
            type="range"
            min={0}
            max={1}
            step={0.05}
            value={rrThreshold}
            onChange={(e) => setRrThreshold(Number(e.target.value))}
            disabled={busy}
            className="mt-2 w-full accent-emerald-600"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            MLT Refinement
          </label>
          <div className="flex items-center gap-3 pt-1">
            <label className="flex cursor-pointer items-center gap-1.5 text-sm text-zinc-300">
              <input
                type="checkbox"
                checked={useMlt}
                onChange={(e) => setUseMlt(e.target.checked)}
                disabled={busy}
                className="rounded border-zinc-600 bg-zinc-950 text-emerald-600 focus:ring-emerald-500"
              />
              On
            </label>
            {useMlt && (
              <input
                type="number"
                min={1}
                max={50}
                value={mltIter}
                onChange={(e) => setMltIter(Number(e.target.value))}
                disabled={busy}
                className="w-16 rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-xs text-zinc-100 outline-none focus:border-emerald-600"
              />
            )}
          </div>
        </div>

        <div className="col-span-2 flex items-end gap-2 sm:col-span-1 lg:col-span-2">
          {busy ? (
            <button
              type="button"
              onClick={onStop}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
            >
              <Square className="size-4" />
              Stop
            </button>
          ) : (
            <button
              type="button"
              onClick={handleRun}
              disabled={!brief.trim()}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-50"
            >
              <Play className="size-4" />
              Run Pipeline
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
