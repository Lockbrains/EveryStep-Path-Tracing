"use client";

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  Gauge,
  Palette,
  LayoutList,
  FileText,
} from "lucide-react";
import type { BenchmarkData } from "@/lib/types";

function WeightBar({ weight }: { weight: number }) {
  const pct = Math.round(weight * 100);
  const color =
    weight >= 0.2
      ? "bg-indigo-400"
      : weight >= 0.1
        ? "bg-indigo-500/70"
        : "bg-zinc-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-20 overflow-hidden rounded-full bg-zinc-800">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="min-w-[2rem] text-right text-xs tabular-nums text-zinc-300">
        {weight.toFixed(2)}
      </span>
    </div>
  );
}

function SectionHeader({
  icon: Icon,
  label,
}: {
  icon: typeof Gauge;
  label: string;
}) {
  return (
    <div className="mb-3 flex items-center gap-2 border-b border-zinc-700/50 pb-2">
      <Icon className="size-4 text-indigo-400" />
      <span className="text-xs font-semibold uppercase tracking-wider text-zinc-300">
        {label}
      </span>
    </div>
  );
}

export function BenchmarkPanel({ data }: { data: BenchmarkData | null }) {
  const [expanded, setExpanded] = useState(true);

  if (!data) return null;

  return (
    <section className="rounded-xl border border-zinc-700/60 bg-zinc-900 p-5">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 text-left"
      >
        {expanded ? (
          <ChevronDown className="size-4 text-indigo-400" />
        ) : (
          <ChevronRight className="size-4 text-indigo-400" />
        )}
        <span className="text-sm font-semibold text-zinc-100">
          Benchmark System
        </span>
        <span className="text-xs text-zinc-500">(backward path analysis)</span>
        <span className="ml-auto rounded-full bg-indigo-900/40 px-2.5 py-0.5 text-xs font-medium text-indigo-300">
          {data.n_dimensions} dimensions
        </span>
      </button>

      {expanded && (
        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div>
            <SectionHeader icon={Gauge} label="Quality Dimensions" />
            <div className="space-y-1">
              {data.dimensions.map((d) => (
                <details key={d.name} className="group rounded-lg border border-zinc-800 bg-zinc-950/60">
                  <summary className="flex cursor-pointer items-center justify-between px-3 py-2.5 marker:[content:'']">
                    <span className="text-sm font-medium text-zinc-100">
                      {d.name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
                    </span>
                    <WeightBar weight={d.weight} />
                  </summary>
                  <div className="border-t border-zinc-800 px-3 py-2.5">
                    <p className="text-xs leading-relaxed text-zinc-400">
                      {d.description}
                    </p>
                    {(d.rubric_low || d.rubric_high) && (
                      <div className="mt-2 grid grid-cols-2 gap-2">
                        {d.rubric_low && (
                          <div className="rounded-md bg-red-950/30 px-2 py-1.5">
                            <span className="text-[10px] font-medium text-red-400">Score 0</span>
                            <p className="mt-0.5 text-[11px] leading-snug text-red-300/70">
                              {d.rubric_low}
                            </p>
                          </div>
                        )}
                        {d.rubric_high && (
                          <div className="rounded-md bg-emerald-950/30 px-2 py-1.5">
                            <span className="text-[10px] font-medium text-emerald-400">Score 1</span>
                            <p className="mt-0.5 text-[11px] leading-snug text-emerald-300/70">
                              {d.rubric_high}
                            </p>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </details>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            {data.style_anchors.length > 0 && (
              <div>
                <SectionHeader icon={Palette} label="Style Anchors" />
                <div className="flex flex-wrap gap-2">
                  {data.style_anchors.map((a, i) => (
                    <span
                      key={i}
                      className="rounded-full border border-zinc-700 bg-zinc-800 px-3 py-1 text-xs text-zinc-200"
                    >
                      {a}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {data.structural_patterns.length > 0 && (
              <div>
                <SectionHeader icon={LayoutList} label="Structural Patterns" />
                <ol className="space-y-1.5 pl-1">
                  {data.structural_patterns.map((p, i) => (
                    <li key={i} className="flex gap-2 text-xs leading-relaxed text-zinc-300">
                      <span className="mt-px flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-zinc-800 text-[10px] font-medium text-zinc-400">
                        {i + 1}
                      </span>
                      {p}
                    </li>
                  ))}
                </ol>
              </div>
            )}

            {data.reference_summaries.length > 0 && (
              <div>
                <SectionHeader icon={FileText} label="Reference Summaries" />
                <div className="space-y-2">
                  {data.reference_summaries.map((s, i) => (
                    <p
                      key={i}
                      className="rounded-lg border border-zinc-800 bg-zinc-950/60 px-3 py-2 text-xs leading-relaxed text-zinc-300"
                    >
                      {s}
                    </p>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
