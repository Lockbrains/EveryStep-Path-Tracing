"use client";

import { CheckCircle2, XCircle, Eye, EyeOff, RotateCcw } from "lucide-react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { DimensionScore, SampleData, StepState } from "@/lib/types";
import { MoodBoardGrid } from "./MoodBoardGrid";

function ScoreBar({ score, label }: { score: number; label?: string }) {
  const pct = Math.round(score * 100);
  const color =
    score >= 0.7
      ? "bg-emerald-500"
      : score >= 0.4
        ? "bg-amber-500"
        : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      {label && (
        <span className="w-28 shrink-0 truncate text-[10px] text-zinc-500">
          {label}
        </span>
      )}
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-10 text-right text-[10px] tabular-nums text-zinc-400">
        {score.toFixed(2)}
      </span>
    </div>
  );
}

function DimensionRadar({ dims }: { dims: DimensionScore[] }) {
  if (dims.length < 3) return null;

  const data = dims.map((d) => ({
    dim:
      d.dimension.length > 12
        ? d.dimension.slice(0, 12) + "\u2026"
        : d.dimension,
    score: d.score,
    fullMark: 1.0,
  }));

  return (
    <ResponsiveContainer width="100%" height={200}>
      <RadarChart data={data} cx="50%" cy="50%" outerRadius="70%">
        <PolarGrid stroke="#3f3f46" />
        <PolarAngleAxis
          dataKey="dim"
          tick={{ fontSize: 9, fill: "#a1a1aa" }}
        />
        <PolarRadiusAxis domain={[0, 1]} tick={false} axisLine={false} />
        <Tooltip
          contentStyle={{
            background: "#18181b",
            border: "1px solid #3f3f46",
            fontSize: 11,
          }}
          formatter={(v) => `${Number(v).toFixed(3)}`}
        />
        <Radar
          dataKey="score"
          stroke="#818cf8"
          fill="#818cf8"
          fillOpacity={0.3}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}

function CandidateCard({
  sample,
  index,
  isBest,
}: {
  sample: SampleData;
  index: number;
  isBest: boolean;
}) {
  return (
    <div
      className={`rounded-lg border p-2 ${isBest ? "border-emerald-600/60 bg-emerald-950/10" : "border-zinc-800 bg-zinc-950/50"}`}
    >
      <div className="mb-1 flex items-center justify-between">
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${isBest ? "bg-emerald-900/50 text-emerald-400" : "bg-zinc-800 text-zinc-300"}`}
        >
          #{index + 1} {isBest && "\u2713 Best"}
        </span>
        <span className="text-[10px] tabular-nums text-zinc-500">
          {sample.nImages} img
        </span>
      </div>
      <MoodBoardGrid
        imageIds={sample.imageIds}
        annotation={sample.annotation}
        compact
        highlight={isBest}
      />
    </div>
  );
}

export function StepDetail({ step }: { step: StepState | null }) {
  if (!step)
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-600">
        Click a step above to inspect details
      </div>
    );

  const bestIdx = step.scoring?.best_index ?? 0;

  return (
    <div className="flex flex-col gap-4 overflow-y-auto">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-zinc-200">
          Step {step.step}: {step.title}
        </h3>
        <div className="flex items-center gap-2">
          {step.attempt > 0 && (
            <span className="flex items-center gap-1 rounded-full bg-amber-900/40 px-2 py-0.5 text-[10px] text-amber-400">
              <RotateCcw className="size-3" />
              retry #{step.attempt}
            </span>
          )}
          <span className="rounded-full border border-zinc-700 bg-zinc-800 px-2.5 py-0.5 text-xs text-zinc-400">
            {step.status}
          </span>
        </div>
      </div>

      {step.scoring && step.scoring.exclusion_violations && step.scoring.exclusion_violations.length > 0 && (
        <div className="rounded-lg border-2 border-red-600 bg-red-950/50 p-4">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-xl">&#x1F6A8;</span>
            <span className="text-sm font-black uppercase tracking-wider text-red-300">
              FORBIDDEN ELEMENT VIOLATIONS
            </span>
            <span className="ml-auto rounded bg-red-800 px-2 py-0.5 text-xs font-bold text-red-200">
              SCORE CAPPED TO 0.3
            </span>
          </div>
          <div className="space-y-1.5">
            {step.scoring.exclusion_violations.map((v, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded-md border border-red-700 bg-red-900/40 px-3 py-2"
              >
                <span className="text-base text-red-400">&#x2718;</span>
                <span className="text-sm font-bold text-red-100">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {step.scoring && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
              Scoring ({step.scoring.n_candidates} candidates)
            </p>
            <span className={`text-xs font-semibold tabular-nums ${
              step.scoring.exclusion_violations && step.scoring.exclusion_violations.length > 0
                ? "text-red-400"
                : "text-emerald-400"
            }`}>
              best: {step.scoring.best_aggregate.toFixed(3)}
              {step.scoring.exclusion_violations && step.scoring.exclusion_violations.length > 0 && " (PENALIZED)"}
            </span>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            <DimensionRadar dims={step.scoring.best_dimensions} />
            <div className="space-y-1">
              {step.scoring.best_dimensions.map((d) => (
                <div key={d.dimension}>
                  <ScoreBar score={d.score} label={d.dimension} />
                  {d.suggestion && d.score < 0.7 && (
                    <p className="ml-[7.5rem] text-[9px] italic text-zinc-600">
                      {d.suggestion}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>

          {step.scoring.all_aggregates.length > 1 && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] text-zinc-600">All scores:</span>
              <div className="flex gap-1">
                {step.scoring.all_aggregates.map((a, i) => (
                  <span
                    key={i}
                    className={`rounded px-1.5 py-0.5 text-[10px] tabular-nums ${
                      i === bestIdx
                        ? "bg-emerald-900/40 text-emerald-400"
                        : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {a.toFixed(3)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {step.shadowRay && (
        <div
          className={`flex items-start gap-2 rounded-lg border p-3 ${
            step.shadowRay.visible
              ? "border-emerald-800/50 bg-emerald-950/20"
              : "border-orange-800/50 bg-orange-950/20"
          }`}
        >
          {step.shadowRay.visible ? (
            <Eye className="mt-0.5 size-4 shrink-0 text-emerald-500" />
          ) : (
            <EyeOff className="mt-0.5 size-4 shrink-0 text-orange-500" />
          )}
          <div className="text-xs">
            <span className="font-medium text-zinc-200">
              Shadow Ray: {step.shadowRay.visible ? "VISIBLE" : "OCCLUDED"}
            </span>
            {step.shadowRay.alignment_score != null && (
              <span className="ml-2 text-zinc-400">
                Alignment: {(step.shadowRay.alignment_score * 100).toFixed(0)}%
              </span>
            )}
            {step.shadowRay.occlusion_reasons.length > 0 && (
              <ul className="mt-1 space-y-0.5 text-[10px] text-orange-400/80">
                {step.shadowRay.occlusion_reasons.map((r, i) => (
                  <li key={i}>&middot; {r}</li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {step.rr && (
        <div
          className={`flex items-center gap-2 rounded-lg border p-3 ${
            step.rr.continue
              ? "border-emerald-800/50 bg-emerald-950/20"
              : "border-red-800/50 bg-red-950/20"
          }`}
        >
          {step.rr.continue ? (
            <CheckCircle2 className="size-4 shrink-0 text-emerald-500" />
          ) : (
            <XCircle className="size-4 shrink-0 text-red-500" />
          )}
          <div className="text-xs">
            <span className="font-medium text-zinc-200">
              Russian Roulette:{" "}
              {step.rr.continue ? "CONTINUE" : "TERMINATED"}
            </span>
            <span className="ml-2 text-zinc-500">
              q={step.rr.survival_probability.toFixed(3)} w=
              {step.rr.weight.toFixed(3)} score={step.rr.score.toFixed(3)}
            </span>
          </div>
        </div>
      )}

      {step.boardImageIds.length > 0 && step.status === "complete" && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            Selected Mood Board
          </p>
          <MoodBoardGrid
            imageIds={step.boardImageIds}
            annotation={step.boardAnnotation}
            highlight
          />
        </div>
      )}

      {step.samples.length > 0 ? (
        <div>
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            Candidates ({step.samples.length})
          </p>
          <div className="grid gap-2 sm:grid-cols-2">
            {step.samples.map((s, i) => (
              <CandidateCard
                key={i}
                sample={s}
                index={i}
                isBest={i === bestIdx}
              />
            ))}
          </div>
        </div>
      ) : (
        step.status === "running" && (
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span className="inline-block size-2 animate-pulse rounded-full bg-amber-400" />
            Generating mood board candidates...
          </div>
        )
      )}
    </div>
  );
}
