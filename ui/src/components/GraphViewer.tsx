"use client";

import { useEffect, useRef, useState } from "react";
import cytoscape, { Core } from "cytoscape";
import { Experiment, PhaseMeasurement, SelectedElement } from "@/types/graph";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const cytoscapeDagre = require("cytoscape-dagre");

if (typeof cytoscape("core", "dagre") === "undefined") {
  cytoscape.use(cytoscapeDagre);
}

interface GraphViewerProps {
  experiment: Experiment | null;
  onSelect: (sel: SelectedElement) => void;
  onHover: (sel: SelectedElement) => void;
}

function truncate(s: string | null | undefined, n: number): string {
  if (!s) return "";
  return s.length > n ? s.slice(0, n) + "\u2026" : s;
}

function configLabel(phase: PhaseMeasurement): string {
  const parts: string[] = [];
  if (phase.name) parts.push(phase.name);
  if (phase.struct && phase.struct !== phase.name) parts.push(phase.struct);
  const tags = phase.tags?.join(", ");
  if (tags && tags !== phase.name && tags !== phase.struct) parts.push(tags);
  return parts.length > 0 ? parts.join(", ") : "phase";
}

export default function GraphViewer({
  experiment,
  onSelect,
  onHover,
}: GraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectRef = useRef(onSelect);
  const onHoverRef = useRef(onHover);
  const [showConfigs, setShowConfigs] = useState(true);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { onHoverRef.current = onHover; }, [onHover]);

  useEffect(() => {
    if (!containerRef.current || !experiment) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const elements: any[] = [];

    for (const node of experiment.nodes) {
      elements.push({
        group: "nodes",
        data: {
          id: node.id,
          label: truncate(node.label, 30),
          fullLabel: node.label,
          type: node.type,
          nodeType: node.type,
          name: node.name,
          measurements: node.measurements ?? [],
          materials: node.materials ?? null,
          source_code: node.source_code ?? null,
          start_line: node.start_line ?? null,
          end_line: node.end_line ?? null,
        },
      });
    }

    for (const edge of experiment.edges) {
      elements.push({
        group: "edges",
        data: {
          id: edge.source + "->" + edge.target,
          source: edge.source,
          target: edge.target,
          label: edge.label,
          process_steps: edge.process_steps ?? [],
          source_code: edge.source_code ?? null,
          start_line: edge.start_line ?? null,
          end_line: edge.end_line ?? null,
        },
      });
    }

    // Add config nodes when toggled on
    if (showConfigs) {
      for (const node of experiment.nodes) {
        const phases = (node.measurements ?? []).filter(
          (m): m is PhaseMeasurement => m.type === "phase"
        );
        if (phases.length === 0) continue;

        const phaseByName = new Map<string, PhaseMeasurement>();
        for (const p of phases) {
          if (p.name) phaseByName.set(p.name, p);
        }

        for (let i = 0; i < phases.length; i++) {
          const phase = phases[i];
          const configId = `config-${node.id}-${i}`;
          const label = configLabel(phase);

          elements.push({
            group: "nodes",
            data: {
              id: configId,
              label: truncate(label, 30),
              fullLabel: label,
              nodeType: "config",
              type: "config",
              phase,
              materialNodeData: node,
            },
          });

          if (phase.within && phaseByName.has(phase.within)) {
            const parentIdx = phases.indexOf(phaseByName.get(phase.within)!);
            const parentId = `config-${node.id}-${parentIdx}`;
            elements.push({
              group: "edges",
              data: {
                id: `${parentId}->${configId}`,
                source: parentId,
                target: configId,
                isConfigEdge: true,
              },
            });
          } else {
            elements.push({
              group: "edges",
              data: {
                id: `${node.id}->${configId}`,
                source: node.id,
                target: configId,
                isConfigEdge: true,
              },
            });
          }
        }
      }
    }

    if (cyRef.current) cyRef.current.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "text-valign": "center",
            "text-halign": "center",
            "font-size": "11px",
            color: "#e6edf3",
            "text-wrap": "wrap",
            "text-max-width": "120px",
            width: "140px",
            height: "50px",
            shape: "round-rectangle",
            "background-color": "#1f6feb",
            "border-width": 2,
            "border-color": "#388bfd",
            "text-outline-color": "#1f6feb",
            "text-outline-width": 1,
          },
        },
        {
          selector: 'node[type="raw_material"]',
          style: {
            "background-color": "#da3633",
            "border-color": "#f85149",
            "text-outline-color": "#da3633",
            shape: "round-rectangle",
          },
        },
        {
          selector: 'node[type="material"]',
          style: {
            "background-color": "#1f6feb",
            "border-color": "#388bfd",
            "text-outline-color": "#1f6feb",
          },
        },
        {
          selector: 'node[type="config"]',
          style: {
            "background-color": "#8957e5",
            "border-color": "#a371f7",
            "text-outline-color": "#8957e5",
            width: "120px",
            height: "40px",
            "font-size": "10px",
          },
        },
        {
          selector: "node:active, node:selected",
          style: {
            "border-color": "#f0f6fc",
            "border-width": 3,
          },
        },
        {
          selector: "node.hover",
          style: {
            "border-color": "#79c0ff",
            "border-width": 3,
          },
        },
        {
          selector: "edge",
          style: {
            label: "data(label)",
            "font-size": "10px",
            color: "#8b949e",
            "text-rotation": "autorotate",
            "text-margin-y": -10,
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#30363d",
            "line-color": "#30363d",
            width: 2,
            "text-outline-color": "#0d1117",
            "text-outline-width": 2,
          },
        },
        {
          selector: "edge[?isConfigEdge]",
          style: {
            "line-color": "#a371f7",
            "target-arrow-color": "#a371f7",
            "line-style": "dashed",
            width: 1.5,
            "events": "no" as any,
          },
        },
        {
          selector: "edge.hover",
          style: {
            "line-color": "#58a6ff",
            "target-arrow-color": "#58a6ff",
            width: 3,
            color: "#e6edf3",
          },
        },
        {
          selector: "edge.selected",
          style: {
            "line-color": "#58a6ff",
            "target-arrow-color": "#58a6ff",
            width: 3,
            color: "#e6edf3",
          },
        },
      ],
      layout: {
        name: "dagre",
        rankDir: "LR",
        nodeSep: 60,
        rankSep: 120,
        edgeSep: 30,
        padding: 40,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any,
      minZoom: 0.2,
      maxZoom: 4,
    });

    cyRef.current = cy;

    // Node hover — show details in sidebar
    cy.on("mouseover", "node", (e) => {
      const node = e.target;
      node.addClass("hover");
      const d = node.data();
      if (d.nodeType === "config") {
        onHoverRef.current({
          kind: "config",
          data: d.phase,
          parentLabel: d.materialNodeData.label,
        });
      } else {
        onHoverRef.current({
          kind: "node",
          data: {
            id: d.id,
            type: d.type,
            label: d.fullLabel,
            name: d.name,
            measurements: d.measurements,
            materials: d.materials,
            source_code: d.source_code,
            start_line: d.start_line,
            end_line: d.end_line,
          },
        });
      }
    });
    cy.on("mouseout", "node", (e) => {
      e.target.removeClass("hover");
      onHoverRef.current(null);
    });

    // Edge hover — show details in sidebar
    cy.on("mouseover", "edge", (e) => {
      const edge = e.target;
      const d = edge.data();
      if (d.isConfigEdge) return; // config edges are not interactive
      edge.addClass("hover");
      const srcNode = cy.getElementById(d.source);
      const tgtNode = cy.getElementById(d.target);
      const sourceLabel = srcNode.length
        ? srcNode.data("fullLabel")
        : d.source;
      const targetLabel = tgtNode.length
        ? tgtNode.data("fullLabel")
        : d.target;
      onHoverRef.current({
        kind: "edge",
        data: {
          source: d.source,
          target: d.target,
          label: d.label,
          process_steps: d.process_steps,
          source_code: d.source_code,
          start_line: d.start_line,
          end_line: d.end_line,
          sourceLabel,
          targetLabel,
        },
      });
    });
    cy.on("mouseout", "edge", (e) => {
      e.target.removeClass("hover");
      onHoverRef.current(null);
    });

    // Node click
    cy.on("tap", "node", (e) => {
      cy.edges().removeClass("selected");
      const d = e.target.data();
      if (d.nodeType === "config") {
        onSelectRef.current({
          kind: "config",
          data: d.phase,
          parentLabel: d.materialNodeData.label,
        });
      } else {
        onSelectRef.current({
          kind: "node",
          data: {
            id: d.id,
            type: d.type,
            label: d.fullLabel,
            name: d.name,
            measurements: d.measurements,
            materials: d.materials,
            source_code: d.source_code,
            start_line: d.start_line,
            end_line: d.end_line,
          },
        });
      }
    });

    // Edge click
    cy.on("tap", "edge", (e) => {
      const d = e.target.data();
      if (d.isConfigEdge) return; // config edges are not interactive
      cy.edges().removeClass("selected");
      e.target.addClass("selected");
      const srcNode = cy.getElementById(d.source);
      const tgtNode = cy.getElementById(d.target);
      const sourceLabel = srcNode.length
        ? srcNode.data("fullLabel")
        : d.source;
      const targetLabel = tgtNode.length
        ? tgtNode.data("fullLabel")
        : d.target;
      onSelectRef.current({
        kind: "edge",
        data: {
          source: d.source,
          target: d.target,
          label: d.label,
          process_steps: d.process_steps,
          source_code: d.source_code,
          start_line: d.start_line,
          end_line: d.end_line,
          sourceLabel,
          targetLabel,
        },
      });
    });

    // Background click
    cy.on("tap", (e) => {
      if (e.target === cy) {
        cy.edges().removeClass("selected");
        onSelectRef.current(null);
      }
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [experiment, showConfigs]);

  return (
    <div className="relative h-full w-full bg-[#0d1117]">
      <div ref={containerRef} className="h-full w-full" />
      <button
        onClick={() => setShowConfigs((v) => !v)}
        className={`absolute top-3 right-3 z-10 rounded-md border px-2.5 py-1.5 text-xs cursor-pointer transition-colors ${
          showConfigs
            ? "border-[#a371f7] bg-[#8957e5] text-white"
            : "border-[#30363d] bg-[#161b22] text-[#8b949e] hover:border-[#a371f7] hover:text-[#c9d1d9]"
        }`}
      >
        {showConfigs ? "Hide Phases" : "Show Phases"}
      </button>
    </div>
  );
}
