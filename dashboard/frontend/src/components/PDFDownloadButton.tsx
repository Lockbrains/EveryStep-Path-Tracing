"use client";

import { useState } from "react";
import { pdf } from "@react-pdf/renderer";
import { FileDown, Loader2 } from "lucide-react";
import { ArtBiblePDF } from "./ArtBiblePDF";
import { imageUrl } from "@/lib/api";
import type { BoardData, BenchmarkData, StepState } from "@/lib/types";

interface PDFDownloadButtonProps {
  title: string;
  steps: StepState[];
  boards: BoardData[];
  benchmark?: BenchmarkData | null;
  disabled?: boolean;
}

async function prefetchImageAsDataUri(id: string): Promise<string> {
  try {
    const res = await fetch(imageUrl(id));
    if (!res.ok) return "";
    const blob = await res.blob();
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result as string);
      reader.onerror = () => resolve("");
      reader.readAsDataURL(blob);
    });
  } catch {
    return "";
  }
}

async function buildImageMap(
  steps: StepState[],
  boards: BoardData[],
): Promise<Record<string, string>> {
  const allIds = new Set<string>();
  for (const s of steps) {
    for (const id of s.boardImageIds) allIds.add(id);
  }
  for (const b of boards) {
    for (const id of b.imageIds) allIds.add(id);
  }

  const entries = await Promise.all(
    [...allIds].map(async (id) => [id, await prefetchImageAsDataUri(id)] as const),
  );
  return Object.fromEntries(entries.filter(([, uri]) => uri));
}

export function PDFDownloadButton({
  title,
  steps,
  boards,
  benchmark,
  disabled,
}: PDFDownloadButtonProps) {
  const [generating, setGenerating] = useState(false);

  const completedCount = steps.filter((s) => s.status === "complete").length;
  const isDisabled = disabled || generating || completedCount === 0;

  async function handleDownload() {
    setGenerating(true);
    try {
      const imageMap = await buildImageMap(steps, boards);

      const doc = (
        <ArtBiblePDF
          title={title}
          steps={steps}
          boards={boards}
          benchmark={benchmark}
          imageMap={imageMap}
        />
      );
      const blob = await pdf(doc).toBlob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ArtBible_${title.replace(/\s+/g, "_").slice(0, 40)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("PDF generation failed:", err);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={isDisabled}
      className={`inline-flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-medium transition-all ${
        isDisabled
          ? "cursor-not-allowed bg-zinc-800 text-zinc-600"
          : "bg-indigo-600 text-white hover:bg-indigo-500"
      }`}
    >
      {generating ? (
        <Loader2 className="size-3.5 animate-spin" />
      ) : (
        <FileDown className="size-3.5" />
      )}
      {generating ? "Generating PDF..." : "Download PDF"}
    </button>
  );
}
