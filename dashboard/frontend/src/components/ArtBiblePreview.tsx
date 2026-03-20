"use client";

import ReactMarkdown from "react-markdown";

export type ArtBibleSection = {
  title: string;
  content: string;
  status: "pending" | "generating" | "complete" | "mutating";
  quality: number;
  version: number;
};

const BADGE: Record<ArtBibleSection["status"], string> = {
  pending: "bg-zinc-700 text-zinc-200",
  generating: "animate-pulse bg-amber-500/25 text-amber-300 ring-1 ring-amber-500/40",
  complete: "bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-500/30",
  mutating: "bg-blue-500/20 text-blue-300 ring-1 ring-blue-500/30",
};

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

export function ArtBiblePreview({ sections = [] }: { sections?: ArtBibleSection[] }) {
  if (sections.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-lg border border-zinc-800 bg-zinc-900 text-sm text-zinc-500">
        No sections
      </div>
    );
  }

  return (
    <div className="max-h-[min(70vh,640px)] overflow-y-auto rounded-lg border border-zinc-800 bg-zinc-900 p-3">
      <div className="flex flex-col gap-3">
        {sections.map((s, i) => (
          <article key={`${s.title}-${i}`} className="rounded-lg border border-zinc-800 bg-zinc-800/60 p-4">
            {s.status === "generating" ? (
              <div className="mb-3 h-0.5 w-full animate-pulse rounded-full bg-amber-500/45" aria-hidden />
            ) : null}
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-zinc-100">{s.title}</h3>
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${BADGE[s.status]}`}>{s.status}</span>
              <span className="ml-auto text-xs text-zinc-500">v{s.version}</span>
            </div>
            <div className="text-sm text-zinc-300 [&_a]:text-emerald-400 [&_a]:underline [&_h2]:mb-2 [&_h2]:mt-3 [&_h2]:text-base [&_h2]:font-semibold [&_h2]:text-zinc-100 [&_h3]:mb-1 [&_h3]:mt-2 [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-zinc-100">
              <ReactMarkdown
                components={{
                  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                  ul: ({ children }) => <ul className="mb-2 list-inside list-disc">{children}</ul>,
                  ol: ({ children }) => <ol className="mb-2 list-inside list-decimal">{children}</ol>,
                  li: ({ children }) => <li className="mb-1">{children}</li>,
                  code: ({ children }) => (
                    <code className="rounded bg-zinc-900 px-1 py-0.5 font-mono text-xs text-amber-200">{children}</code>
                  ),
                }}
              >
                {s.content || "_Empty_"}
              </ReactMarkdown>
            </div>
            <div className="mt-3">
              <div className="mb-1 flex justify-between text-xs text-zinc-500">
                <span>quality</span>
                <span>{(clamp01(s.quality) * 100).toFixed(0)}%</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded bg-zinc-900">
                <div
                  className="h-full rounded bg-emerald-500 transition-all duration-500"
                  style={{ width: `${clamp01(s.quality) * 100}%` }}
                />
              </div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
