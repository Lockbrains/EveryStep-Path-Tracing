"use client";

import {
  BarChart,
  Bar,
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { MLTData, StepState } from "@/lib/types";

interface QualityPoint {
  step: string;
  bestQ: number;
  avgQ: number;
}

interface RRPoint {
  step: string;
  samples: number;
  survived: number;
  pruned: number;
  retries: number;
  images: number;
}

function buildData(steps: StepState[]) {
  const quality: QualityPoint[] = [];
  const rr: RRPoint[] = [];

  for (const s of steps) {
    if (s.status === "pending") continue;
    const aggregates = s.scoring?.all_aggregates ?? [];
    const best =
      aggregates.length > 0
        ? Math.max(...aggregates)
        : (s.finalScore ?? 0);
    const avg =
      aggregates.length > 0
        ? aggregates.reduce((a, b) => a + b, 0) / aggregates.length
        : best;

    quality.push({ step: `S${s.step}`, bestQ: best, avgQ: avg });

    const survived = s.rr?.continue ? 1 : 0;
    rr.push({
      step: `S${s.step}`,
      samples: s.samples.length,
      survived,
      pruned: s.rr && !s.rr.continue ? 1 : 0,
      retries: s.attempt,
      images: s.boardImageIds.length,
    });
  }

  return { quality, rr };
}

export function MetricsChart({
  steps,
  mlt,
}: {
  steps: StepState[];
  mlt?: MLTData | null;
}) {
  const { quality, rr } = buildData(steps);

  if (quality.length === 0) {
    return (
      <div className="flex h-full min-h-[120px] items-center justify-center text-sm text-zinc-600">
        Metrics will appear as the pipeline progresses
      </div>
    );
  }

  const mltData =
    mlt?.score_history?.map((sc, i) => ({ iter: i, score: sc })) ?? [];

  return (
    <div
      className={`grid gap-4 ${mltData.length > 0 ? "sm:grid-cols-2 lg:grid-cols-3" : "sm:grid-cols-2"}`}
    >
      <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
          Quality per Step
        </p>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={quality}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="step" tick={{ fontSize: 10, fill: "#71717a" }} />
            <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: "#71717a" }} />
            <Tooltip
              contentStyle={{
                background: "#18181b",
                border: "1px solid #3f3f46",
                fontSize: 11,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Line
              type="monotone"
              dataKey="bestQ"
              name="Best"
              stroke="#10b981"
              strokeWidth={2}
              dot={{ r: 3 }}
            />
            <Line
              type="monotone"
              dataKey="avgQ"
              name="Avg"
              stroke="#f59e0b"
              strokeWidth={1.5}
              strokeDasharray="4 2"
              dot={{ r: 2 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
          Samples, RR & Images
        </p>
        <ResponsiveContainer width="100%" height={160}>
          <BarChart data={rr}>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis dataKey="step" tick={{ fontSize: 10, fill: "#71717a" }} />
            <YAxis
              allowDecimals={false}
              tick={{ fontSize: 10, fill: "#71717a" }}
            />
            <Tooltip
              contentStyle={{
                background: "#18181b",
                border: "1px solid #3f3f46",
                fontSize: 11,
              }}
            />
            <Legend wrapperStyle={{ fontSize: 10 }} />
            <Bar
              dataKey="samples"
              name="Samples"
              fill="#3b82f6"
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="images"
              name="Images"
              fill="#8b5cf6"
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="survived"
              name="RR Pass"
              fill="#10b981"
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="pruned"
              name="RR Cut"
              fill="#ef4444"
              radius={[2, 2, 0, 0]}
            />
            <Bar
              dataKey="retries"
              name="Retries"
              fill="#f59e0b"
              radius={[2, 2, 0, 0]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {mltData.length > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-3">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-zinc-500">
            MLT Refinement ({mlt?.accepted ?? 0}A / {mlt?.rejected ?? 0}R)
          </p>
          <ResponsiveContainer width="100%" height={160}>
            <LineChart data={mltData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis
                dataKey="iter"
                tick={{ fontSize: 10, fill: "#71717a" }}
              />
              <YAxis
                domain={[0, 1]}
                tick={{ fontSize: 10, fill: "#71717a" }}
              />
              <Tooltip
                contentStyle={{
                  background: "#18181b",
                  border: "1px solid #3f3f46",
                  fontSize: 11,
                }}
              />
              <Line
                type="monotone"
                dataKey="score"
                name="Quality"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={{ r: 2 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
