export type Strategy = "naive" | "importance" | "mis" | "nee";

export interface PipelineConfig {
  brief: string;
  references: string[];
  image_refs: string[];
  n_samples: number;
  strategies: [Strategy];
  rr_threshold: number;
  use_mlt: boolean;
  mlt_iterations: number;
}

export interface DimensionScore {
  dimension: string;
  score: number;
  reasoning: string;
  suggestion: string;
}

export interface SampleData {
  candidateIndex: number;
  annotation: string;
  nImages: number;
  imageIds: string[];
}

export interface ScoringData {
  n_candidates: number;
  best_index: number;
  best_aggregate: number;
  best_dimensions: DimensionScore[];
  all_aggregates: number[];
  best_image_ids: string[];
  exclusion_violations: string[];
}

export interface ShadowRayData {
  visible: boolean;
  alignment_score: number;
  occlusion_reasons: string[];
}

export interface RRDecision {
  continue: boolean;
  weight: number;
  survival_probability: number;
  score: number;
  attempt: number;
}

export interface BenchmarkDimension {
  name: string;
  description: string;
  weight: number;
  rubric_low: string;
  rubric_high: string;
}

export interface BenchmarkData {
  n_dimensions: number;
  dimensions: BenchmarkDimension[];
  style_anchors: string[];
  style_exclusions: string[];
  structural_patterns: string[];
  reference_summaries: string[];
}

export interface MLTData {
  accepted: number;
  rejected: number;
  score_history: number[];
  final_aggregate: number | null;
}

export interface BoardData {
  stepIndex: number;
  annotation: string;
  imageIds: string[];
  nImages: number;
  score: number;
}

export type StepStatus = "pending" | "running" | "complete" | "retrying";

export interface StepState {
  step: number;
  title: string;
  status: StepStatus;
  samples: SampleData[];
  scoring: ScoringData | null;
  shadowRay: ShadowRayData | null;
  rr: RRDecision | null;
  boardImageIds: string[];
  boardAnnotation: string;
  finalScore: number | null;
  finalDimensions: Array<{ dimension: string; score: number }>;
  attempt: number;
}

export type RunStatus = "idle" | "running" | "complete" | "error";

export interface PipelineState {
  runStatus: RunStatus;
  benchmark: BenchmarkData | null;
  steps: StepState[];
  boards: BoardData[];
  pathScores: number[];
  mlt: MLTData | null;
  error: string | null;
}

export const STEP_TITLES = [
  "Worldview & Setting",
  "Color Palette & Visual Tone",
  "Material & Texture Specifications",
  "Character Design Guidelines",
  "Environment & Architecture Rules",
] as const;

export function initialPipelineState(): PipelineState {
  return {
    runStatus: "idle",
    benchmark: null,
    steps: STEP_TITLES.map((title, i) => ({
      step: i + 1,
      title,
      status: "pending",
      samples: [],
      scoring: null,
      shadowRay: null,
      rr: null,
      boardImageIds: [],
      boardAnnotation: "",
      finalScore: null,
      finalDimensions: [],
      attempt: 0,
    })),
    boards: [],
    pathScores: [],
    mlt: null,
    error: null,
  };
}
