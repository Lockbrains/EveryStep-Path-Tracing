"use client";

import { useState } from "react";
import { ShieldAlert, Copy, Check } from "lucide-react";

function buildChallengePrompt(term: string): string {
  return (
    `你生成的图像违反了以下明确禁止的规则：\n\n` +
    `  ❌ "${term}"\n\n` +
    `这条规则来自参考图分析。参考图中完全没有这个元素。\n` +
    `请解释：\n` +
    `1. 你是否在生成时注意到了这条禁止规则？\n` +
    `2. 如果注意到了，为什么最终结果仍然包含这个元素？\n` +
    `3. 请重新生成，严格确保这个元素不出现。`
  );
}

function ForbiddenTag({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleClick = async () => {
    try {
      await navigator.clipboard.writeText(buildChallengePrompt(text));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard API unavailable */
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      title="Click to copy challenge prompt"
      className="group relative flex items-center gap-2.5 rounded-lg border-2 border-red-700/80 bg-red-950/60 px-4 py-3 text-left transition-all hover:border-red-500 hover:bg-red-900/50 active:scale-[0.98]"
    >
      <span className="text-xl text-red-400">&#x26D4;</span>
      <span className="text-sm font-bold leading-snug text-red-100">
        {text}
      </span>
      <span className="ml-auto shrink-0 opacity-0 transition-opacity group-hover:opacity-100">
        {copied ? (
          <Check className="size-4 text-emerald-400" />
        ) : (
          <Copy className="size-4 text-red-400/60" />
        )}
      </span>
      {copied && (
        <span className="absolute -top-2 right-2 rounded bg-zinc-800 px-2 py-0.5 text-[10px] font-medium text-emerald-400 shadow-lg">
          Copied!
        </span>
      )}
    </button>
  );
}

export function ForbiddenBanner({
  exclusions,
  violations,
}: {
  exclusions: string[];
  violations?: string[];
}) {
  if (!exclusions || exclusions.length === 0) return null;

  const violationSet = new Set(
    (violations ?? []).map((v) => v.toLowerCase()),
  );

  return (
    <section className="rounded-xl border-2 border-red-700/70 bg-gradient-to-r from-red-950/80 via-red-950/60 to-red-950/80 p-5 shadow-[0_0_30px_-5px_rgba(220,38,38,0.3)]">
      <div className="mb-4 flex items-center gap-3">
        <div className="flex size-10 items-center justify-center rounded-lg bg-red-900/60 shadow-inner">
          <ShieldAlert className="size-6 text-red-400" />
        </div>
        <div>
          <h2 className="text-base font-black uppercase tracking-wider text-red-300">
            Forbidden Elements
          </h2>
          <p className="text-xs text-red-400/70">
            Click any item to copy a challenge prompt for the LLM
          </p>
        </div>
        <span className="ml-auto rounded-full bg-red-900/60 px-3 py-1 text-xs font-bold tabular-nums text-red-300">
          {exclusions.length} rules
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {exclusions.map((e, i) => (
          <ForbiddenTag key={i} text={e} />
        ))}
      </div>

      {violations && violations.length > 0 && (
        <div className="mt-4 rounded-lg border-2 border-red-500 bg-red-900/40 p-4 animate-pulse">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-2xl">&#x1F6A8;</span>
            <span className="text-sm font-black uppercase tracking-wider text-red-200">
              Active Violations Detected
            </span>
          </div>
          <div className="flex flex-wrap gap-2">
            {violations.map((v, i) => (
              <span
                key={i}
                className="rounded-md border border-red-400 bg-red-800/60 px-3 py-1.5 text-sm font-bold text-red-100 shadow-lg"
              >
                &#x2718; {v}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
