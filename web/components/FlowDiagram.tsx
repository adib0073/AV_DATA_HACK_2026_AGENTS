"use client";

import { useMemo } from "react";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from "reactflow";
import "reactflow/dist/style.css";

import type { FlowGraph, FlowNodeKind, GraphNode } from "@/lib/types";

const COL_WIDTH = 220;
const ROW_HEIGHT = 78;

const KIND_STYLE: Record<FlowNodeKind, { bg: string; border: string; text: string; tag: string }> = {
  user: { bg: "#0b1220", border: "#475569", text: "#e2e8f0", tag: "" },
  orchestrator: { bg: "#1e1b4b", border: "#6366f1", text: "#e0e7ff", tag: "Layer 3" },
  agent: { bg: "#0c1a2e", border: "#3b82f6", text: "#dbeafe", tag: "Layer 3" },
  gateway: { bg: "#04211d", border: "#14b8a6", text: "#99f6e4", tag: "Layer 4" },
  server: { bg: "#111827", border: "#64748b", text: "#e2e8f0", tag: "MCP" },
  tool: { bg: "#0b1220", border: "#334155", text: "#94a3b8", tag: "" },
};

/** Custom node: shows label + sublabel + a layer/kind tag, lights up when fired. */
function FlowNode({ data }: NodeProps) {
  const k = KIND_STYLE[data.kind as FlowNodeKind];
  const fired = data.fired as boolean;
  return (
    <div
      style={{
        background: k.bg,
        border: `1.5px solid ${fired ? "#22c55e" : k.border}`,
        boxShadow: fired ? "0 0 0 3px rgba(34,197,94,0.18)" : "none",
        color: k.text,
        borderRadius: 10,
        padding: "8px 12px",
        width: 168,
        opacity: data.dim && !fired ? 0.55 : 1,
      }}
    >
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ fontSize: 12.5, fontWeight: 600, lineHeight: 1.2 }}>{data.label}</span>
        {fired && (
          <span style={{ marginLeft: "auto", height: 7, width: 7, borderRadius: 999, background: "#22c55e" }} />
        )}
      </div>
      {data.sublabel && (
        <div style={{ fontSize: 10, opacity: 0.75, marginTop: 2 }}>{data.sublabel}</div>
      )}
      {k.tag && (
        <div style={{ fontSize: 8.5, letterSpacing: 0.4, textTransform: "uppercase", opacity: 0.55, marginTop: 3 }}>
          {k.tag}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes = { flow: FlowNode };

function layout(graph: FlowGraph): { nodes: Node[]; edges: Edge[] } {
  const byCol = new Map<number, GraphNode[]>();
  for (const n of graph.nodes) {
    const arr = byCol.get(n.col) ?? [];
    arr.push(n);
    byCol.set(n.col, arr);
  }
  for (const arr of byCol.values()) arr.sort((a, b) => a.order - b.order);
  const maxRows = Math.max(...Array.from(byCol.values(), (a) => a.length), 1);

  const pos = new Map<string, { x: number; y: number }>();
  for (const [col, arr] of byCol) {
    const startY = ((maxRows - arr.length) / 2) * ROW_HEIGHT;
    arr.forEach((n, rank) => {
      pos.set(n.id, { x: col * COL_WIDTH, y: startY + rank * ROW_HEIGHT });
    });
  }

  const anyFired = graph.nodes.some((n) => n.fired);
  const nodes: Node[] = graph.nodes.map((n) => ({
    id: n.id,
    type: "flow",
    position: pos.get(n.id)!,
    data: { ...n, dim: graph.ran && anyFired },
    sourcePosition: Position.Right,
    targetPosition: Position.Left,
  }));

  const edges: Edge[] = graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    type: "smoothstep",
    animated: e.fired,
    style: {
      stroke: e.fired ? "#22c55e" : "#334155",
      strokeWidth: e.fired ? 2 : 1,
      opacity: graph.ran && anyFired && !e.fired ? 0.4 : 1,
    },
  }));

  return { nodes, edges };
}

export default function FlowDiagram({ graph }: { graph: FlowGraph }) {
  const { nodes, edges } = useMemo(() => layout(graph), [graph]);

  return (
    <div style={{ height: 460 }} className="rounded-lg border border-white/10 bg-black/30">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={false}
        minZoom={0.3}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="#1e293b" />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
