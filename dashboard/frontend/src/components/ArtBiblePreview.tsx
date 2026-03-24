"use client";

import { useEffect, useRef } from "react";
import type { BoardData, StepState } from "@/lib/types";
import { MoodBoardGrid } from "./MoodBoardGrid";

interface ArtBiblePreviewProps {
  steps: StepState[];
  boards: BoardData[];
}

export function ArtBiblePreview({ steps, boards }: ArtBiblePreviewProps) {
  const endRef = useRef<HTMLDivElement>(null);
  const completedSteps = steps.filter((s) => s.status === "complete");

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [completedSteps.length]);

  if (completedSteps.length === 0) {
    return (
      <div className="flex h-full min-h-[200px] items-center justify-center text-sm text-zinc-600">
        Mood boards will appear here as the pipeline generates them
      </div>
    );
  }

  return (
    <div className="space-y-4 overflow-y-auto">
      {completedSteps.map((s) => {
        const board = boards.find((b) => b.stepIndex === s.step - 1);
        const imgIds = board?.imageIds ?? s.boardImageIds;
        const annotation = board?.annotation ?? s.boardAnnotation;

        return (
          <div
            key={s.step}
            className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <h4 className="text-xs font-semibold text-zinc-200">
                <span className="mr-1.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-zinc-800 text-[10px] tabular-nums text-zinc-400">
                  {s.step}
                </span>
                {s.title}
              </h4>
              {s.finalScore != null && (
                <span className="rounded bg-zinc-800 px-1.5 py-0.5 text-[10px] tabular-nums text-zinc-400">
                  Q: {s.finalScore.toFixed(3)}
                </span>
              )}
            </div>

            <MoodBoardGrid imageIds={imgIds} annotation={annotation} />

            {s.finalDimensions.length > 0 && (
              <div className="mt-3 flex flex-wrap gap-1.5">
                {s.finalDimensions.map((d) => (
                  <span
                    key={d.dimension}
                    className={`rounded-full px-2 py-0.5 text-[9px] ${
                      d.score >= 0.7
                        ? "bg-emerald-900/30 text-emerald-400"
                        : d.score >= 0.4
                          ? "bg-amber-900/30 text-amber-400"
                          : "bg-red-900/30 text-red-400"
                    }`}
                  >
                    {d.dimension}: {d.score.toFixed(2)}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
      <div ref={endRef} />
    </div>
  );
}
