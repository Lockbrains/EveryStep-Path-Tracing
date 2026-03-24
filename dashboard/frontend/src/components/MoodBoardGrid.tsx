"use client";

import { useState } from "react";
import { imageUrl } from "@/lib/api";

interface MoodBoardGridProps {
  imageIds: string[];
  annotation?: string;
  compact?: boolean;
  highlight?: boolean;
  dimmed?: boolean;
}

export function MoodBoardGrid({
  imageIds,
  annotation,
  compact = false,
  highlight = false,
  dimmed = false,
}: MoodBoardGridProps) {
  const [enlarged, setEnlarged] = useState<string | null>(null);

  if (imageIds.length === 0 && !annotation) {
    return (
      <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-zinc-700 text-xs text-zinc-600">
        No images generated
      </div>
    );
  }

  const gridClass =
    imageIds.length <= 2
      ? "grid-cols-2"
      : imageIds.length === 3
        ? "grid-cols-3"
        : "grid-cols-2";

  return (
    <div
      className={`relative rounded-lg border p-2 transition-all ${
        highlight
          ? "border-emerald-600/60 ring-1 ring-emerald-500/30"
          : dimmed
            ? "border-zinc-800 opacity-40"
            : "border-zinc-800"
      }`}
    >
      {imageIds.length > 0 && (
        <div
          className={`grid gap-1.5 ${gridClass} ${compact ? "max-h-40" : ""}`}
        >
          {imageIds.map((id) => (
            <button
              key={id}
              type="button"
              onClick={() => setEnlarged(enlarged === id ? null : id)}
              className="group relative aspect-square overflow-hidden rounded-md bg-zinc-900"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={imageUrl(id)}
                alt=""
                className="h-full w-full object-cover transition-transform group-hover:scale-105"
                loading="lazy"
              />
            </button>
          ))}
        </div>
      )}

      {annotation && (
        <p
          className={`mt-2 leading-relaxed text-zinc-400 ${compact ? "line-clamp-2 text-[10px]" : "text-xs"}`}
        >
          {annotation}
        </p>
      )}

      {enlarged && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm"
          onClick={() => setEnlarged(null)}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={imageUrl(enlarged)}
            alt=""
            className="max-h-[80vh] max-w-[80vw] rounded-lg shadow-2xl"
          />
        </div>
      )}
    </div>
  );
}
