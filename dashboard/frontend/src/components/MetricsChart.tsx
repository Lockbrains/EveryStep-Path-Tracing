"use client";

import { useId } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type MetricsSnapshot = {
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
};

const axisTick = { fill: "#a1a1aa", fontSize: 11 };
const gridStroke = "#27272a";
const tooltipStyle = {
  backgroundColor: "#18181b",
  border: "1px solid #3f3f46",
  borderRadius: 8,
  color: "#f4f4f5",
};

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="flex h-full min-h-[200px] items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900 text-sm text-zinc-500">
      {label}
    </div>
  );
}

export function MetricsChart({ snapshots = [] }: { snapshots?: MetricsSnapshot[] }) {
  const costGradId = `esCostFill-${useId().replace(/:/g, "")}`;
  const qualityData = snapshots.map((s) => ({
    totalSamples: s.totalSamples,
    bestQuality: s.bestQuality,
    averageQuality: s.averageQuality,
  }));

  const costData = snapshots.map((s) => ({
    totalSamples: s.totalSamples,
    totalCost: s.totalCost,
  }));

  const pathData = snapshots.map((s) => ({
    timestamp: s.timestamp,
    active: s.pathsActive,
    terminated: s.pathsTerminated,
    accepted: s.pathsAccepted,
  }));

  const lastMis = snapshots.length ? snapshots[snapshots.length - 1]!.misWeights : { free: 0, rag: 0, tool: 0 };
  const pieData = [
    { name: "free", value: lastMis.free, fill: "#3b82f6" },
    { name: "rag", value: lastMis.rag, fill: "#f59e0b" },
    { name: "tool", value: lastMis.tool, fill: "#10b981" },
  ];
  const pieSum = pieData.reduce((a, b) => a + b.value, 0);

  return (
    <div className="grid w-full grid-cols-1 gap-4 md:grid-cols-2">
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
        <div className="mb-2 text-sm font-medium text-zinc-100">Quality Convergence (SPP analogue)</div>
        {qualityData.length === 0 ? (
          <EmptyPanel label="No data" />
        ) : (
          <div className="h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={qualityData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
                <XAxis dataKey="totalSamples" type="number" tick={axisTick} stroke="#3f3f46" />
                <YAxis domain={[0, 1]} tick={axisTick} stroke="#3f3f46" width={36} />
                <Tooltip contentStyle={tooltipStyle} labelStyle={{ color: "#e4e4e7" }} />
                <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: 12 }} />
                <Line type="monotone" dataKey="bestQuality" name="best" stroke="#10b981" strokeWidth={2} dot={false} isAnimationActive />
                <Line type="monotone" dataKey="averageQuality" name="average" stroke="#a1a1aa" strokeWidth={2} dot={false} isAnimationActive />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
        <div className="mb-2 text-sm font-medium text-zinc-100">Cumulative Token Cost</div>
        {costData.length === 0 ? (
          <EmptyPanel label="No data" />
        ) : (
          <div className="h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={costData} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={costGradId} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.55} />
                    <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.05} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
                <XAxis dataKey="totalSamples" type="number" tick={axisTick} stroke="#3f3f46" />
                <YAxis tick={axisTick} stroke="#3f3f46" width={44} />
                <Tooltip contentStyle={tooltipStyle} />
                <Area type="monotone" dataKey="totalCost" stroke="#f59e0b" fill={`url(#${costGradId})`} strokeWidth={2} isAnimationActive />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
        <div className="mb-2 text-sm font-medium text-zinc-100">Path Exploration</div>
        {pathData.length === 0 ? (
          <EmptyPanel label="No data" />
        ) : (
          <div className="h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={pathData} margin={{ top: 8, right: 12, left: 0, bottom: 24 }}>
                <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
                <XAxis dataKey="timestamp" tick={axisTick} stroke="#3f3f46" interval="preserveStartEnd" />
                <YAxis tick={axisTick} stroke="#3f3f46" width={36} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: 12 }} />
                <Bar dataKey="active" name="active" stackId="paths" fill="#71717a" isAnimationActive />
                <Bar dataKey="terminated" name="terminated" stackId="paths" fill="#ef4444" isAnimationActive />
                <Bar dataKey="accepted" name="accepted" stackId="paths" fill="#10b981" isAnimationActive />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-3">
        <div className="mb-2 text-sm font-medium text-zinc-100">MIS Strategy Distribution</div>
        {pieSum <= 0 ? (
          <EmptyPanel label="No data" />
        ) : (
          <div className="h-[220px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip contentStyle={tooltipStyle} />
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={72} paddingAngle={2} isAnimationActive>
                  {pieData.map((e) => (
                    <Cell key={e.name} fill={e.fill} stroke="#27272a" strokeWidth={1} />
                  ))}
                </Pie>
                <Legend wrapperStyle={{ color: "#a1a1aa", fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
