"use client";

import * as d3 from "d3";
import { useCallback, useEffect, useRef, useState } from "react";

export type PathNode = {
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
};

const STATUS_FILL: Record<PathNode["status"], string> = {
  active: "#a1a1aa",
  accepted: "#10b981",
  rejected: "#ef4444",
  terminated: "#52525b",
};

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}

function qualityRadius(q: number): number {
  return 4 + 8 * clamp01(q);
}

function buildRoot(nodes: PathNode[]): PathNode | null {
  if (nodes.length === 0) return null;
  const anyChildren = nodes.some((n) => (n.children?.length ?? 0) > 0);
  if (anyChildren) {
    const roots = nodes.filter((n) => n.parentId === null);
    if (roots.length === 1) return roots[0];
    return {
      id: "__virtual_root",
      parentId: null,
      step: -1,
      stepName: "",
      content: "",
      quality: 0,
      cost: 0,
      strategy: "free",
      status: "terminated",
      children: roots,
    };
  }
  const map = new Map<string, PathNode>();
  for (const n of nodes) {
    map.set(n.id, {
      ...n,
      children: [],
    });
  }
  const roots: PathNode[] = [];
  for (const n of map.values()) {
    if (n.parentId && map.has(n.parentId)) {
      map.get(n.parentId)!.children.push(n);
    } else {
      roots.push(n);
    }
  }
  if (roots.length === 0) return null;
  if (roots.length === 1) return roots[0];
  return {
    id: "__virtual_root",
    parentId: null,
    step: -1,
    stepName: "",
    content: "",
    quality: 0,
    cost: 0,
    strategy: "free",
    status: "terminated",
    children: roots,
  };
}

type TooltipState = {
  visible: boolean;
  x: number;
  y: number;
  node: PathNode | null;
};

export function PathTree({
  nodes = [],
  width: widthProp,
  height: heightProp,
}: {
  nodes?: PathNode[];
  width?: number;
  height?: number;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const [dims, setDims] = useState({ w: widthProp ?? 640, h: heightProp ?? 360 });
  const [tip, setTip] = useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    node: null,
  });

  const onResize = useCallback(() => {
    if (!wrapRef.current) return;
    const r = wrapRef.current.getBoundingClientRect();
    const w = widthProp ?? Math.max(280, r.width);
    const h = heightProp ?? Math.max(200, r.height);
    setDims({ w, h });
  }, [widthProp, heightProp]);

  useEffect(() => {
    onResize();
    const el = wrapRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => onResize());
    ro.observe(el);
    return () => ro.disconnect();
  }, [onResize]);

  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const rootData = buildRoot(nodes);
    const margin = { top: 24, right: 24, bottom: 24, left: 24 };
    const innerW = dims.w - margin.left - margin.right;
    const innerH = dims.h - margin.top - margin.bottom;

    d3.select(svg).selectAll("*").remove();

    if (!rootData) {
      d3.select(svg)
        .attr("width", dims.w)
        .attr("height", dims.h)
        .append("text")
        .attr("x", dims.w / 2)
        .attr("y", dims.h / 2)
        .attr("text-anchor", "middle")
        .attr("fill", "#71717a")
        .attr("font-size", 14)
        .text("No path data");
      return;
    }

    const hierarchy = d3.hierarchy<PathNode>(rootData, (d) => d.children);
    const treeLayout = d3.tree<PathNode>().size([innerW, innerH]);
    const layoutRoot = treeLayout(hierarchy);

    const g = d3
      .select(svg)
      .attr("width", dims.w)
      .attr("height", dims.h)
      .attr("class", "text-zinc-100")
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    const links = layoutRoot.links();

    const linkGen = d3
      .linkVertical<d3.HierarchyPointLink<PathNode>, d3.HierarchyPointNode<PathNode>>()
      .x((d) => d.x)
      .y((d) => d.y);

    const linkSel = g
      .selectAll<SVGPathElement, d3.HierarchyPointLink<PathNode>>("path.link")
      .data(links, (d) => `${d.source.data.id}-${d.target.data.id}`);

    linkSel
      .exit()
      .transition()
      .duration(400)
      .attr("stroke-opacity", 0)
      .remove();

    const linkEnter = linkSel
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("fill", "none")
      .attr("stroke", "#3f3f46")
      .attr("stroke-width", 1.5)
      .attr("stroke-opacity", 0)
      .attr("d", (d) => linkGen(d) ?? "");

    linkEnter
      .transition()
      .duration(600)
      .attr("stroke-opacity", (d) => 0.15 + 0.85 * clamp01(d.target.data.quality))
      .attr("d", (d) => linkGen(d) ?? "");

    linkSel
      .transition()
      .duration(600)
      .attr("stroke-opacity", (d) => 0.15 + 0.85 * clamp01(d.target.data.quality))
      .attr("d", (d) => linkGen(d) ?? "");

    const nodeSel = g
      .selectAll<SVGGElement, d3.HierarchyPointNode<PathNode>>("g.node")
      .data(layoutRoot.descendants(), (d) => d.data.id);

    nodeSel.exit().transition().duration(400).style("opacity", 0).remove();

    function shapeTag(s: PathNode["strategy"]): "circle" | "rect" | "path" {
      if (s === "free") return "circle";
      if (s === "rag") return "rect";
      return "path";
    }

    function applyShape(
      gNode: d3.Selection<
        SVGGElement,
        d3.HierarchyPointNode<PathNode>,
        d3.BaseType,
        unknown
      >,
      d: d3.HierarchyPointNode<PathNode>,
    ) {
      if (d.data.id.startsWith("__")) {
        gNode.selectAll("circle,rect,path").remove();
        return;
      }
      const r = qualityRadius(d.data.quality);
      const fill = STATUS_FILL[d.data.status];
      const want = shapeTag(d.data.strategy);
      const first = gNode.select<SVGElement>("circle,rect,path");
      const cur = first.empty() ? null : first.node()!.tagName.toLowerCase();
      if (cur !== want) {
        gNode.selectAll("circle,rect,path").remove();
        if (want === "circle") {
          gNode.append("circle").attr("stroke", "#27272a").attr("stroke-width", 1);
        } else if (want === "rect") {
          gNode.append("rect").attr("stroke", "#27272a").attr("stroke-width", 1);
        } else {
          gNode.append("path").attr("stroke", "#27272a").attr("stroke-width", 1);
        }
      }
      if (want === "circle") {
        gNode.select("circle").attr("r", r).attr("fill", fill);
      } else if (want === "rect") {
        gNode.select("rect").attr("x", -r).attr("y", -r).attr("width", r * 2).attr("height", r * 2).attr("fill", fill);
      } else {
        const p = r * 1.15;
        gNode
          .select("path")
          .attr("fill", fill)
          .attr("d", `M 0,${-p} L ${p},0 L 0,${p} L ${-p},0 Z`);
      }
    }

    const nodeEnter = nodeSel
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", (d) => `translate(${d.x},${d.y})`)
      .style("opacity", 0)
      .each(function (d) {
        applyShape(d3.select(this), d);
      });

    const merged = nodeEnter.merge(nodeSel);

    merged.each(function (d) {
      applyShape(d3.select(this), d);
    });

    merged.transition().duration(600).attr("transform", (d) => `translate(${d.x},${d.y})`).style("opacity", 1);

    merged
      .style("cursor", (d) => (d.data.id.startsWith("__") ? "default" : "pointer"))
      .on("mouseenter", function (event, d) {
        if (d.data.id.startsWith("__")) return;
        setTip({
          visible: true,
          x: event.clientX,
          y: event.clientY,
          node: d.data,
        });
      })
      .on("mousemove", function (event, d) {
        if (d.data.id.startsWith("__")) return;
        setTip({
          visible: true,
          x: event.clientX,
          y: event.clientY,
          node: d.data,
        });
      })
      .on("mouseleave", () => {
        setTip((s) => ({ ...s, visible: false, node: null }));
      });
  }, [nodes, dims]);

  return (
    <div ref={wrapRef} className="relative h-full min-h-[200px] w-full rounded-md bg-zinc-900">
      <svg ref={svgRef} className="block" role="img" aria-label="Path tree" />
      {tip.visible && tip.node && (
        <div
          className="pointer-events-none fixed z-50 rounded-md border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-100 shadow-lg"
          style={{ left: tip.x + 12, top: tip.y + 12 }}
        >
          <div className="font-medium text-zinc-100">{tip.node.stepName}</div>
          <div className="text-zinc-400">quality: {tip.node.quality.toFixed(2)}</div>
          <div className="text-zinc-400">cost: {tip.node.cost}</div>
          <div className="text-zinc-400">strategy: {tip.node.strategy}</div>
        </div>
      )}
    </div>
  );
}
