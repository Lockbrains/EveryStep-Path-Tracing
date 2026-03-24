"use client";

import { ChevronRight } from "lucide-react";
import type { StepState } from "@/lib/types";
import { imageUrl } from "@/lib/api";

function statusColor(s: StepState): string {
  if (s.status === "retrying") return "border-amber-500/60 bg-amber-950/30";
  if (s.status === "complete" && s.rr && !s.rr.continue)
    return "border-red-500/60 bg-red-950/40";
  if (s.status === "complete") return "border-emerald-500/60 bg-emerald-950/30";
  if (s.status === "running") return "border-amber-500/60 bg-amber-950/30";
  return "border-zinc-700 bg-zinc-900";
}

function qualityBar(score: number | null): string {
  if (score == null) return "0%";
  return `${Math.round(score * 100)}%`;
}

function qualityColor(score: number | null): string {
  if (score == null) return "bg-zinc-700";
  if (score >= 0.7) return "bg-emerald-500";
  if (score >= 0.4) return "bg-amber-500";
  return "bg-red-500";
}

export function StepTimeline({
  steps,
  selectedStep,
  onSelectStep,
}: {
  steps: StepState[];
  selectedStep: number | null;
  onSelectStep: (step: number) => void;
}) {
  return (
    <div className="flex items-stretch gap-1 overflow-x-auto py-1">
      {steps.map((s, i) => {
        const active = selectedStep === s.step;
        const thumbId = s.boardImageIds[0];
        return (
          <div key={s.step} className="flex items-center gap-1">
            {i > 0 && (
              <ChevronRight
                className="size-4 shrink-0 text-zinc-600"
                aria-hidden
              />
            )}
            <button
              type="button"
              onClick={() => onSelectStep(s.step)}
              className={`relative flex w-[170px] shrink-0 flex-col rounded-xl border p-3 text-left transition-all ${statusColor(s)} ${
                active ? "ring-2 ring-emerald-500/50" : ""
              }`}
            >
              <span className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
                Step {s.step}
              </span>
              <span className="mt-0.5 text-xs font-semibold leading-tight text-zinc-100">
                {s.title}
              </span>

              {thumbId && (
                <div className="mt-2 flex gap-1">
                  {s.boardImageIds.slice(0, 3).map((id) => (
                    <div
                      key={id}
                      className="h-10 w-10 overflow-hidden rounded-md bg-zinc-800"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={imageUrl(id)}
                        alt=""
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    </div>
                  ))}
                  {s.boardImageIds.length > 3 && (
                    <span className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-800 text-[10px] text-zinc-500">
                      +{s.boardImageIds.length - 3}
                    </span>
                  )}
                </div>
              )}

              <div className="mt-2 flex items-center justify-between text-[10px] text-zinc-400">
                <span>
                  {(s.status === "running" || s.status === "retrying") && (
                    <span className="mr-1 inline-block size-1.5 animate-pulse rounded-full bg-amber-400" />
                  )}
                  {s.status === "retrying"
                    ? `retry #${s.attempt}`
                    : s.status}
                </span>
                <span className="tabular-nums">
                  {s.samples.length} sample{s.samples.length !== 1 ? "s" : ""}
                </span>
              </div>

              <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-zinc-800">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${qualityColor(s.finalScore)}`}
                  style={{ width: qualityBar(s.finalScore) }}
                />
              </div>
              {s.finalScore != null && (
                <span className="mt-1 text-right text-[10px] tabular-nums text-zinc-400">
                  Q: {s.finalScore.toFixed(3)}
                </span>
              )}

              {s.rr && !s.rr.continue && (
                <span className="absolute -right-1 -top-1 rounded-full bg-red-600 px-1.5 py-0.5 text-[9px] font-bold text-white">
                  RR CUT
                </span>
              )}
              {s.shadowRay && !s.shadowRay.visible && (
                <span className="absolute -left-1 -top-1 rounded-full bg-orange-600 px-1.5 py-0.5 text-[9px] font-bold text-white">
                  OCCL
                </span>
              )}
            </button>
          </div>
        );
      })}
    </div>
  );
}
