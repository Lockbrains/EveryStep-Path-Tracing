"use client";

import "@xyflow/react/dist/style.css";

import {
  Background,
  BaseEdge,
  Controls,
  type Edge,
  type EdgeProps,
  getBezierPath,
  Handle,
  MiniMap,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
} from "@xyflow/react";
import { useCallback, useMemo, type MouseEvent } from "react";

export type StepData = {
  id: string;
  name: string;
  samplesCount: number;
  bestQuality: number;
  avgQuality: number;
  status: "pending" | "running" | "complete";
  tokensCost: number;
};

const PIPELINE_IDS = ["worldview", "palette", "materials", "characters", "environments"] as const;
const DEFAULT_NAMES: Record<(typeof PIPELINE_IDS)[number], string> = {
  worldview: "Worldview",
  palette: "Palette",
  materials: "Materials",
  characters: "Characters",
  environments: "Environments",
};

const TOTAL_SAMPLES_CAP = 500;

function qualityColor(q: number): string {
  if (q >= 0.66) return "#10b981";
  if (q >= 0.33) return "#eab308";
  return "#ef4444";
}

function mergeSteps(steps: StepData[]): Map<string, StepData> {
  const m = new Map<string, StepData>();
  for (const id of PIPELINE_IDS) {
    m.set(id, {
      id,
      name: DEFAULT_NAMES[id],
      samplesCount: 0,
      bestQuality: 0,
      avgQuality: 0,
      status: "pending",
      tokensCost: 0,
    });
  }
  for (const s of steps) {
    if (m.has(s.id)) m.set(s.id, { ...m.get(s.id)!, ...s });
  }
  return m;
}

type PipelineNodeData = StepData & { totalCap: number };

function PipelineStepNode({ data, selected }: NodeProps<Node<PipelineNodeData>>) {
  const q = data.bestQuality;
  const bar = Math.round(clamp01(q) * 100);
  return (
    <div
      className={`min-w-[150px] rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-zinc-100 shadow-md ${
        selected ? "ring-2 ring-emerald-500/60" : ""
      }`}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-zinc-600 !bg-zinc-500" />
      <div className="text-sm font-bold text-zinc-100">{data.name}</div>
      <div className="mt-1 text-xs text-zinc-400">
        Samples: {data.samplesCount}/{data.totalCap}
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded bg-zinc-900">
        <div className="h-full rounded transition-all duration-500" style={{ width: `${bar}%`, backgroundColor: qualityColor(q) }} />
      </div>
      <div className="mt-1 text-xs text-zinc-400">{data.tokensCost.toLocaleString()} tokens</div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-zinc-600 !bg-zinc-500" />
    </div>
  );
}

function ValidatorNode({ selected }: NodeProps<Node<Record<string, never>>>) {
  return (
    <div
      className={`flex h-10 w-10 items-center justify-center ${
        selected ? "opacity-100" : "opacity-90"
      }`}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-zinc-600 !bg-zinc-500" />
      <div
        className="h-6 w-6 rotate-45 border border-zinc-600 bg-zinc-800"
        style={{ borderRadius: 2 }}
      />
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-zinc-600 !bg-zinc-500" />
    </div>
  );
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

function QualityEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
}: EdgeProps<Edge<{ q: number; animated: boolean }>>) {
  const [path] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  const q = typeof data?.q === "number" ? data.q : 0.5;
  const stroke = qualityColor(q);
  return (
    <BaseEdge
      id={id}
      path={path}
      markerEnd={markerEnd}
      style={{
        ...style,
        stroke,
        strokeWidth: 2,
        strokeOpacity: 0.35 + 0.65 * clamp01(q),
        strokeDasharray: data?.animated ? "10 6" : undefined,
        animation: data?.animated ? "esFlowDash 1.1s linear infinite" : undefined,
      }}
    />
  );
}

const nodeTypes = {
  pipelineStep: PipelineStepNode,
  validator: ValidatorNode,
};

const edgeTypes = {
  quality: QualityEdge,
};

export function AgentDAG({
  steps = [],
  onStepClick,
}: {
  steps?: StepData[];
  onStepClick?: (stepId: string) => void;
}) {
  const merged = useMemo(() => mergeSteps(steps), [steps]);
  const totalCap = useMemo(() => {
    const maxS = Math.max(TOTAL_SAMPLES_CAP, ...[...merged.values()].map((s) => s.samplesCount));
    return maxS;
  }, [merged]);

  const { nodes, edges } = useMemo(() => {
    const ns: Node[] = [];
    const es: Edge[] = [];
    const yMain = 40;
    const yVal = 140;
    const x0 = 0;
    const gap = 200;
    for (let i = 0; i < PIPELINE_IDS.length; i++) {
      const id = PIPELINE_IDS[i];
      const sd = merged.get(id)!;
      ns.push({
        id,
        type: "pipelineStep",
        position: { x: x0 + i * gap, y: yMain },
        data: { ...sd, totalCap },
      });
      if (i < PIPELINE_IDS.length - 1) {
        const vid = `val-${id}`;
        ns.push({
          id: vid,
          type: "validator",
          position: { x: x0 + i * gap + gap * 0.45, y: yVal },
          data: {},
        });
        const next = PIPELINE_IDS[i + 1];
        const targetRunning = merged.get(next)?.status === "running";
        const q = (sd.avgQuality + merged.get(next)!.avgQuality) / 2;
        es.push({
          id: `e-${id}-${vid}`,
          source: id,
          target: vid,
          type: "quality",
          data: { q, animated: sd.status === "running" },
        });
        es.push({
          id: `e-${vid}-${next}`,
          source: vid,
          target: next,
          type: "quality",
          data: { q, animated: targetRunning },
        });
      }
    }
    return { nodes: ns, edges: es };
  }, [merged, totalCap]);

  const pipelineSet = useMemo(() => new Set<string>(PIPELINE_IDS), []);

  const onNodeClick = useCallback(
    (_: MouseEvent, n: Node) => {
      if (pipelineSet.has(n.id)) onStepClick?.(n.id);
    },
    [onStepClick, pipelineSet],
  );

  return (
    <div className="h-[420px] w-full rounded-md border border-zinc-800 bg-zinc-900">
      <style>{`@keyframes esFlowDash{to{stroke-dashoffset:-32}}`}</style>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        onNodeClick={onNodeClick}
        proOptions={{ hideAttribution: true }}
        className="bg-zinc-900"
      >
        <Background color="#3f3f46" gap={18} size={1} />
        <MiniMap
          className="!rounded-md !border !border-zinc-700 !bg-zinc-800"
          nodeColor={() => "#52525b"}
          maskColor="rgba(24,24,27,0.85)"
        />
        <Controls className="!border-zinc-700 !bg-zinc-800 [&_button]:!border-zinc-600 [&_button]:!bg-zinc-800 [&_svg]:!fill-zinc-200" />
      </ReactFlow>
    </div>
  );
}
