"use client";

import { useState } from "react";
import { Link2 } from "lucide-react";

export default function ComparePage() {
  const [synced, setSynced] = useState(true);

  return (
    <div className="flex min-h-full flex-col p-6">
      <h1 className="text-xl font-semibold tracking-tight text-zinc-100">
        Compare
      </h1>
      <p className="mt-1 text-sm text-zinc-500">
        Path tracing vs agent workflow — side-by-side visualization
      </p>

      <div className="relative mt-6 flex min-h-[420px] flex-1 gap-0">
        <div className="flex min-h-0 flex-1 flex-col rounded-l-xl border border-r-0 border-zinc-800 bg-zinc-900">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h2 className="text-sm font-semibold text-zinc-100">
              Path tracing
            </h2>
          </div>
          <div className="flex flex-1 items-center justify-center bg-zinc-950/80 p-4">
            <div className="h-full min-h-[320px] w-full rounded-lg border border-dashed border-zinc-700 bg-zinc-950 text-center text-sm text-zinc-500 flex items-center justify-center">
              2D ray tracing animation placeholder
            </div>
          </div>
        </div>

        <div className="relative z-10 flex w-14 shrink-0 flex-col items-center justify-center border-y border-zinc-800 bg-zinc-950">
          <div className="absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-zinc-800" />
          <button
            type="button"
            onClick={() => setSynced((s) => !s)}
            className={`relative flex flex-col items-center gap-1 rounded-lg border px-2 py-3 text-xs font-medium transition-colors ${
              synced
                ? "border-emerald-600/50 bg-emerald-950/40 text-emerald-400"
                : "border-zinc-700 bg-zinc-900 text-zinc-400"
            }`}
            aria-pressed={synced}
          >
            <Link2 className="size-4" aria-hidden />
            Sync
          </button>
        </div>

        <div className="flex min-h-0 flex-1 flex-col rounded-r-xl border border-l-0 border-zinc-800 bg-zinc-900">
          <div className="border-b border-zinc-800 px-4 py-3">
            <h2 className="text-sm font-semibold text-zinc-100">
              Agent workflow
            </h2>
          </div>
          <div className="flex flex-1 items-center justify-center bg-zinc-950/80 p-4">
            <div className="h-full min-h-[320px] w-full rounded-lg border border-dashed border-zinc-700 bg-zinc-950 text-center text-sm text-zinc-500 flex items-center justify-center">
              Agent execution animation placeholder
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-zinc-800 bg-zinc-900 px-4 py-3 text-sm leading-relaxed text-zinc-400">
        <p>
          Monte Carlo path tracing explores light paths through a scene; here,
          each branch is an agent decision, Russian roulette prunes weak paths,
          and MIS combines strategies—so rendering intuition maps directly to
          workflow exploration and Art Bible quality.
        </p>
      </div>
    </div>
  );
}
