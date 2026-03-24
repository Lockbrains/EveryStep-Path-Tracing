"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { startPipeline, streamPipeline } from "@/lib/api";
import type { PipelineEvent } from "@/lib/api";
import type {
  BoardData,
  BenchmarkData,
  DimensionScore,
  MLTData,
  PipelineConfig,
  PipelineState,
  RRDecision,
  SampleData,
  ScoringData,
  ShadowRayData,
} from "@/lib/types";
import { initialPipelineState } from "@/lib/types";
import { ApiKeyPanel } from "@/components/ApiKeyPanel";
import { ConfigBar } from "@/components/ConfigBar";
import { ForbiddenBanner } from "@/components/ForbiddenBanner";
import { BenchmarkPanel } from "@/components/BenchmarkPanel";
import { StepTimeline } from "@/components/StepTimeline";
import { StepDetail } from "@/components/StepDetail";
import { ArtBiblePreview } from "@/components/ArtBiblePreview";
import { MetricsChart } from "@/components/MetricsChart";
import { PDFDownloadButton } from "@/components/PDFDownloadButton";

type Action =
  | { type: "RESET" }
  | { type: "RESTORE"; state: PipelineState }
  | { type: "RUN_START" }
  | { type: "RUN_DONE" }
  | { type: "RUN_ERROR"; error: string }
  | { type: "BENCHMARK_COMPLETE"; data: BenchmarkData }
  | { type: "STEP_START"; step: number; title: string }
  | { type: "SAMPLE_GENERATED"; step: number; sample: SampleData }
  | { type: "SCORING_COMPLETE"; step: number; scoring: ScoringData }
  | { type: "SHADOW_RAY"; step: number; data: ShadowRayData }
  | { type: "RR_DECISION"; step: number; rr: RRDecision }
  | { type: "STEP_RETRY"; step: number; attempt: number }
  | {
      type: "STEP_COMPLETE";
      step: number;
      annotation: string;
      boardImageIds: string[];
      score: number;
      dimensions: Array<{ dimension: string; score: number }>;
      attempt: number;
    }
  | { type: "MLT_COMPLETE"; data: MLTData }
  | {
      type: "PATH_COMPLETE";
      boards: BoardData[];
      pathScores: number[];
      mlt: MLTData | null;
    };

function reducer(state: PipelineState, action: Action): PipelineState {
  switch (action.type) {
    case "RESET":
      return initialPipelineState();

    case "RESTORE":
      return action.state;

    case "RUN_START":
      return { ...initialPipelineState(), runStatus: "running" };

    case "RUN_DONE":
      return { ...state, runStatus: "complete" };

    case "RUN_ERROR":
      return { ...state, runStatus: "error", error: action.error };

    case "BENCHMARK_COMPLETE":
      return { ...state, benchmark: action.data };

    case "STEP_START":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step
            ? {
                ...s,
                status: "running",
                title: action.title || s.title,
                samples: [],
                scoring: null,
                shadowRay: null,
                rr: null,
              }
            : s,
        ),
      };

    case "SAMPLE_GENERATED":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step
            ? { ...s, samples: [...s.samples, action.sample] }
            : s,
        ),
      };

    case "SCORING_COMPLETE":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step ? { ...s, scoring: action.scoring } : s,
        ),
      };

    case "SHADOW_RAY":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step ? { ...s, shadowRay: action.data } : s,
        ),
      };

    case "RR_DECISION":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step ? { ...s, rr: action.rr } : s,
        ),
      };

    case "STEP_RETRY":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step
            ? {
                ...s,
                status: "retrying",
                attempt: action.attempt,
                samples: [],
                scoring: null,
                shadowRay: null,
                rr: null,
              }
            : s,
        ),
      };

    case "STEP_COMPLETE":
      return {
        ...state,
        steps: state.steps.map((s) =>
          s.step === action.step
            ? {
                ...s,
                status: "complete",
                boardAnnotation: action.annotation,
                boardImageIds: action.boardImageIds,
                finalScore: action.score,
                finalDimensions: action.dimensions,
                attempt: action.attempt,
              }
            : s,
        ),
        boards: [
          ...state.boards,
          {
            stepIndex: action.step - 1,
            annotation: action.annotation,
            imageIds: action.boardImageIds,
            nImages: action.boardImageIds.length,
            score: action.score,
          },
        ],
        pathScores: [...state.pathScores, action.score],
      };

    case "MLT_COMPLETE":
      return { ...state, mlt: action.data };

    case "PATH_COMPLETE":
      return {
        ...state,
        runStatus: "complete",
        boards: action.boards,
        pathScores: action.pathScores,
        mlt: action.mlt,
      };

    default:
      return state;
  }
}

function dispatchSSEEvent(
  ev: PipelineEvent,
  dispatch: React.Dispatch<Action>,
) {
  const d = ev.data;
  switch (ev.event_type) {
    case "benchmark_complete":
      dispatch({
        type: "BENCHMARK_COMPLETE",
        data: {
          n_dimensions: (d.n_dimensions as number) ?? 0,
          dimensions: (d.dimensions as BenchmarkData["dimensions"]) ?? [],
          style_anchors: (d.style_anchors as string[]) ?? [],
          style_exclusions: (d.style_exclusions as string[]) ?? [],
          structural_patterns: (d.structural_patterns as string[]) ?? [],
          reference_summaries: (d.reference_summaries as string[]) ?? [],
        },
      });
      break;

    case "step_start":
      dispatch({
        type: "STEP_START",
        step: ev.step,
        title: (d.title as string) ?? "",
      });
      break;

    case "sample_generated":
      dispatch({
        type: "SAMPLE_GENERATED",
        step: ev.step,
        sample: {
          candidateIndex: (d.candidate_index as number) ?? 0,
          annotation: (d.annotation as string) ?? "",
          nImages: (d.n_images as number) ?? 0,
          imageIds: (d.image_ids as string[]) ?? [],
        },
      });
      break;

    case "scoring_complete":
      dispatch({
        type: "SCORING_COMPLETE",
        step: ev.step,
        scoring: {
          n_candidates: (d.n_candidates as number) ?? 0,
          best_index: (d.best_index as number) ?? 0,
          best_aggregate: (d.best_aggregate as number) ?? 0,
          best_dimensions: (d.best_dimensions as DimensionScore[]) ?? [],
          all_aggregates: (d.all_aggregates as number[]) ?? [],
          best_image_ids: (d.best_image_ids as string[]) ?? [],
          exclusion_violations: (d.exclusion_violations as string[]) ?? [],
        },
      });
      break;

    case "shadow_ray":
      dispatch({
        type: "SHADOW_RAY",
        step: ev.step,
        data: {
          visible: (d.visible as boolean) ?? true,
          occlusion_reasons: (d.occlusion_reasons as string[]) ?? [],
        },
      });
      break;

    case "rr_decision":
      dispatch({
        type: "RR_DECISION",
        step: ev.step,
        rr: {
          continue: (d.continue as boolean) ?? true,
          weight: (d.weight as number) ?? 0,
          survival_probability: (d.survival_probability as number) ?? 0,
          score: (d.score as number) ?? 0,
          attempt: (d.attempt as number) ?? 0,
        },
      });
      break;

    case "step_retry":
      dispatch({
        type: "STEP_RETRY",
        step: ev.step,
        attempt: (d.attempt as number) ?? 1,
      });
      break;

    case "step_complete":
      dispatch({
        type: "STEP_COMPLETE",
        step: ev.step,
        annotation: (d.annotation as string) ?? "",
        boardImageIds: (d.board_image_ids as string[]) ?? [],
        score: (d.score as number) ?? 0,
        dimensions:
          (d.dimensions as Array<{ dimension: string; score: number }>) ?? [],
        attempt: (d.attempt as number) ?? 0,
      });
      break;

    case "mlt_complete":
      dispatch({
        type: "MLT_COMPLETE",
        data: {
          accepted: (d.accepted as number) ?? 0,
          rejected: (d.rejected as number) ?? 0,
          score_history: (d.score_history as number[]) ?? [],
          final_aggregate: (d.final_aggregate as number) ?? null,
        },
      });
      break;

    case "path_complete": {
      const rawBoards = (d.boards as Array<Record<string, unknown>>) ?? [];
      dispatch({
        type: "PATH_COMPLETE",
        boards: rawBoards.map((b) => ({
          stepIndex: (b.step_index as number) ?? 0,
          annotation: (b.annotation as string) ?? "",
          imageIds: (b.image_ids as string[]) ?? [],
          nImages: (b.n_images as number) ?? 0,
          score: 0,
        })),
        pathScores: (d.path_scores as number[]) ?? [],
        mlt: (d.mlt as MLTData) ?? null,
      });
      break;
    }
  }
}

const STORAGE_KEY = "everystep_pipeline_state";

export default function DashboardPage() {
  const [state, dispatch] = useReducer(reducer, undefined, initialPipelineState);
  const [selectedStep, setSelectedStep] = useState<number | null>(null);
  const [projectTitle, setProjectTitle] = useState("Untitled Project");
  const stopRef = useRef<(() => void) | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const persisted = JSON.parse(raw) as PipelineState;
        dispatch({ type: "RESTORE", state: persisted });
      }
      const title = localStorage.getItem("everystep_title");
      if (title) setProjectTitle(title);
    } catch { /* ignore */ }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch { /* quota exceeded — ignore */ }
  }, [state, hydrated]);

  const handleRun = useCallback(async (config: PipelineConfig) => {
    const title = config.brief.slice(0, 60);
    setProjectTitle(title);
    try { localStorage.setItem("everystep_title", title); } catch { /* */ }
    stopRef.current?.();
    dispatch({ type: "RUN_START" });
    setSelectedStep(1);

    try {
      const runId = await startPipeline(config);
      const stop = streamPipeline(
        runId,
        (ev) => {
          dispatchSSEEvent(ev, dispatch);
          if (ev.event_type === "step_start") setSelectedStep(ev.step);
        },
        () => dispatch({ type: "RUN_DONE" }),
        () => dispatch({ type: "RUN_ERROR", error: "SSE connection lost" }),
      );
      stopRef.current = stop;
    } catch (err) {
      dispatch({
        type: "RUN_ERROR",
        error: err instanceof Error ? err.message : "Failed to start pipeline",
      });
    }
  }, []);

  const handleStop = useCallback(() => {
    stopRef.current?.();
    stopRef.current = null;
    dispatch({ type: "RUN_DONE" });
  }, []);

  const selectedStepData =
    selectedStep != null
      ? state.steps.find((s) => s.step === selectedStep) ?? null
      : null;

  const completedSteps = state.steps.filter(
    (s) => s.status === "complete",
  ).length;

  return (
    <div className="mx-auto flex min-h-screen max-w-7xl flex-col gap-5 p-5">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight text-zinc-100">
            EveryStep Path Tracing
          </h1>
          <p className="text-xs text-zinc-500">
            Monte Carlo variance reduction for agentic Art Bible generation
          </p>
        </div>
        {state.runStatus !== "idle" && (
          <div className="flex items-center gap-4 text-xs text-zinc-400">
            <span>
              Steps: {completedSteps}/{state.steps.length}
            </span>
            <span>Boards: {state.boards.length}</span>
            {state.benchmark && (
              <span className="text-zinc-500">
                {state.benchmark.n_dimensions} dims
              </span>
            )}
            <span
              className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                state.runStatus === "running"
                  ? "bg-amber-900/40 text-amber-400"
                  : state.runStatus === "complete"
                    ? "bg-emerald-900/40 text-emerald-400"
                    : "bg-red-900/40 text-red-400"
              }`}
            >
              {state.runStatus}
            </span>
          </div>
        )}
      </header>

      <ApiKeyPanel />

      <ConfigBar
        runStatus={state.runStatus}
        onRun={handleRun}
        onStop={handleStop}
      />

      {state.error && (
        <div className="rounded-lg border border-red-800/50 bg-red-950/30 px-4 py-3 text-sm text-red-400">
          {state.error}
        </div>
      )}

      <ForbiddenBanner
        exclusions={state.benchmark?.style_exclusions ?? []}
        violations={
          state.steps
            .flatMap((s) => s.scoring?.exclusion_violations ?? [])
            .filter((v, i, arr) => arr.indexOf(v) === i)
        }
      />

      <BenchmarkPanel data={state.benchmark} />

      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <p className="mb-3 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
          Pipeline Progress
        </p>
        <StepTimeline
          steps={state.steps}
          selectedStep={selectedStep}
          onSelectStep={setSelectedStep}
        />
      </section>

      <div className="grid min-h-[320px] grid-cols-1 gap-5 lg:grid-cols-2">
        <section className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <p className="mb-3 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            Step Detail
          </p>
          <div className="flex-1 overflow-y-auto">
            <StepDetail step={selectedStepData} />
          </div>
        </section>

        <section className="flex flex-col rounded-xl border border-zinc-800 bg-zinc-900 p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[10px] font-medium uppercase tracking-wide text-zinc-500">
              Art Bible Preview
            </p>
            <PDFDownloadButton
              title={projectTitle}
              steps={state.steps}
              boards={state.boards}
              benchmark={state.benchmark}
              disabled={state.runStatus === "running"}
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            <ArtBiblePreview steps={state.steps} boards={state.boards} />
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-zinc-800 bg-zinc-900 p-4">
        <p className="mb-3 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
          Metrics
        </p>
        <MetricsChart steps={state.steps} mlt={state.mlt} />
      </section>
    </div>
  );
}
