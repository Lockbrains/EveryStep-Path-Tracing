"use client";

import { useEffect, useRef } from "react";

function useCanvasLoop(
  draw: (ctx: CanvasRenderingContext2D, w: number, h: number, t: number) => void,
  syncEnabled: boolean,
  offsetMs: number,
) {
  const ref = useRef<HTMLCanvasElement>(null);
  const raf = useRef<number>(0);
  const start = useRef<number>(0);
  const drawRef = useRef(draw);
  drawRef.current = draw;

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const resize = () => {
      const p = canvas.parentElement;
      if (!p) return;
      const r = p.getBoundingClientRect();
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.max(1, Math.floor(r.width * dpr));
      canvas.height = Math.max(1, Math.floor(r.height * dpr));
      canvas.style.width = `${r.width}px`;
      canvas.style.height = `${r.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement!);
    start.current = performance.now();

    const loop = (now: number) => {
      const base = now - start.current;
      const t = syncEnabled ? base : base + offsetMs;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      drawRef.current(ctx, w, h, t);
      raf.current = requestAnimationFrame(loop);
    };
    raf.current = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(raf.current);
      ro.disconnect();
    };
  }, [syncEnabled, offsetMs]);

  return ref;
}

function drawPathTracing(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  ctx.fillStyle = "#18181b";
  ctx.fillRect(0, 0, w, h);

  const floorTop = h - 72;
  ctx.fillStyle = "#27272a";
  ctx.fillRect(32, floorTop, w - 64, h - floorTop - 16);

  ctx.strokeStyle = "#3f3f46";
  ctx.lineWidth = 1;
  ctx.strokeRect(32, floorTop, w - 64, h - floorTop - 16);

  const cx = w * 0.58;
  const cy = h * 0.42;
  const sr = Math.min(48, h * 0.18);
  const grd = ctx.createRadialGradient(cx - sr * 0.3, cy - sr * 0.3, sr * 0.2, cx, cy, sr);
  grd.addColorStop(0, "#52525b");
  grd.addColorStop(1, "#3f3f46");
  ctx.fillStyle = grd;
  ctx.beginPath();
  ctx.arc(cx, cy, sr, 0, Math.PI * 2);
  ctx.fill();

  const lx = w - 72;
  const ly = 56;
  ctx.fillStyle = "#fbbf24";
  ctx.fillRect(lx, ly, 18, 18);

  const camX = w / 2;
  const camY = h - 36;

  const rays = 7;
  for (let i = 0; i < rays; i++) {
    const phase = t * 0.0009 + i * 0.85;
    const ang = -Math.PI * 0.55 + Math.sin(phase) * 0.35;
    const len1 = Math.min(w, h) * 0.22;
    const x1 = camX + Math.cos(ang) * len1;
    const y1 = camY + Math.sin(ang) * len1;

    const accepted = i % 3 !== 1;
    ctx.strokeStyle = accepted ? "#10b981" : "#ef4444";
    ctx.lineWidth = 1.5;
    ctx.setLineDash([]);
    ctx.beginPath();
    ctx.moveTo(camX, camY);
    ctx.lineTo(x1, y1);
    ctx.stroke();

    const bounceAng = ang + (accepted ? 0.9 : 0.2) + Math.sin(phase * 1.3) * 0.2;
    const len2 = Math.min(w, h) * 0.16;
    const x2 = x1 + Math.cos(bounceAng) * len2;
    const y2 = y1 + Math.sin(bounceAng) * len2;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();

    ctx.strokeStyle = "#3b82f6";
    ctx.lineWidth = 1.25;
    ctx.setLineDash([5, 5]);
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(lx + 9, ly + 9);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function roundRectPath(ctx: CanvasRenderingContext2D, x: number, y: number, rw: number, rh: number, r: number) {
  const rr = Math.min(r, rw / 2, rh / 2);
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + rw, y, x + rw, y + rh, rr);
  ctx.arcTo(x + rw, y + rh, x, y + rh, rr);
  ctx.arcTo(x, y + rh, x, y, rr);
  ctx.arcTo(x, y, x + rw, y, rr);
  ctx.closePath();
}

function drawAgentFlow(ctx: CanvasRenderingContext2D, w: number, h: number, t: number) {
  ctx.fillStyle = "#18181b";
  ctx.fillRect(0, 0, w, h);

  const labels = ["Plan", "Tool", "RAG", "Judge", "Commit"];
  const n = labels.length;
  const margin = 40;
  const span = w - margin * 2;
  const gap = span / (n - 1);
  const y = h * 0.42;
  const bw = 68;
  const bh = 36;

  const centers: { x: number; y: number }[] = [];
  for (let i = 0; i < n; i++) {
    const x = margin + i * gap;
    centers.push({ x, y });
    ctx.fillStyle = "#27272a";
    ctx.strokeStyle = "#3f3f46";
    ctx.lineWidth = 1;
    roundRectPath(ctx, x - bw / 2, y - bh / 2, bw, bh, 8);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = "#f4f4f5";
    ctx.font = "12px ui-sans-serif, system-ui";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(labels[i]!, x, y);
  }

  ctx.strokeStyle = "#52525b";
  ctx.lineWidth = 1.5;
  for (let i = 0; i < n - 1; i++) {
    const a = centers[i]!;
    const b = centers[i + 1]!;
    ctx.beginPath();
    ctx.moveTo(a.x + bw / 2, a.y);
    ctx.lineTo(b.x - bw / 2, b.y);
    ctx.stroke();
  }

  const dbX = w - 52;
  const dbY = h * 0.62;
  ctx.fillStyle = "#1f2937";
  ctx.strokeStyle = "#3f3f46";
  roundRectPath(ctx, dbX - 28, dbY - 22, 56, 44, 6);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = "#a1a1aa";
  ctx.font = "10px ui-sans-serif, system-ui";
  ctx.fillText("REF", dbX, dbY - 4);
  ctx.fillText("DB", dbX, dbY + 8);

  const rag = centers[2]!;
  ctx.strokeStyle = "#3b82f6";
  ctx.setLineDash([5, 5]);
  ctx.beginPath();
  ctx.moveTo(rag.x, rag.y + bh / 2);
  ctx.lineTo(dbX, dbY - 22);
  ctx.stroke();
  ctx.setLineDash([]);

  const particles = 14;
  for (let i = 0; i < particles; i++) {
    const u = ((t * 0.00035 + i * 0.07) % 1 + 1) % 1;
    const seg = u * (n - 1);
    const j = Math.floor(seg);
    const f = seg - j;
    const a = centers[j]!;
    const b = centers[j + 1]!;
    const sx = a.x + bw / 2;
    const sy = a.y;
    const ex = b.x - bw / 2;
    const ey = b.y;
    const px = sx + (ex - sx) * f;
    const py = sy + (ey - sy) * f;
    const terminated = i % 4 === 2;
    ctx.fillStyle = terminated ? "#ef4444" : "#10b981";
    ctx.beginPath();
    ctx.arc(px, py, 2.2, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function CompareView({ syncEnabled = true }: { syncEnabled?: boolean }) {
  const leftRef = useCanvasLoop(drawPathTracing, syncEnabled, 0);
  const rightRef = useCanvasLoop(drawAgentFlow, syncEnabled, syncEnabled ? 0 : 380);

  return (
    <div className="grid w-full grid-cols-1 gap-3 lg:grid-cols-2">
      <div className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900">
        <div className="border-b border-zinc-800 px-3 py-2 text-sm font-medium text-zinc-100">Path Tracing</div>
        <div className="relative h-[280px] w-full min-h-[200px]">
          <canvas ref={leftRef} className="absolute inset-0 block h-full w-full" />
        </div>
      </div>
      <div className="flex flex-col rounded-lg border border-zinc-800 bg-zinc-900">
        <div className="border-b border-zinc-800 px-3 py-2 text-sm font-medium text-zinc-100">Agent Workflow</div>
        <div className="relative h-[280px] w-full min-h-[200px]">
          <canvas ref={rightRef} className="absolute inset-0 block h-full w-full" />
        </div>
      </div>
    </div>
  );
}
