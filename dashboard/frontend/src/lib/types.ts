export interface PathNode {
  id: string;
  parentId: string | null;
  step: number;
  stepName: string;
  content: string;
  quality: number;
  cost: number;
  strategy: "free" | "rag" | "tool";
  status: "active" | "accepted" | "rejected" | "terminated";
  children: PathNode[];
}

export interface MetricsSnapshot {
  timestamp: string;
  totalSamples: number;
  bestQuality: number;
  averageQuality: number;
  totalCost: number;
  totalTokens: number;
  pathsActive: number;
  pathsTerminated: number;
  pathsAccepted: number;
  misWeights: { free: number; rag: number; tool: number };
}

export interface ArtBibleSection {
  title: string;
  content: string;
  status: "pending" | "generating" | "complete" | "mutating";
  quality: number;
  version: number;
}

export interface ExperimentConfig {
  experimentId: number;
  name: string;
  task: string;
  models: string[];
  nSamples: number[];
  strategies: string[];
  budget?: number;
  rrThreshold?: number;
}
