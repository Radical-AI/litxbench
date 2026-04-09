"use client";

import { useEffect, useRef } from "react";
import cytoscape, { Core } from "cytoscape";
import { Experiment, PhaseMeasurement, SelectedElement } from "@/types/graph";

// eslint-disable-next-line @typescript-eslint/no-require-imports
const cytoscapeDagre = require("cytoscape-dagre");

if (typeof cytoscape("core", "dagre") === "undefined") {
  cytoscape.use(cytoscapeDagre);
}

interface ConfigGraphViewerProps {
  experiment: Experiment | null;
  onSelect: (sel: SelectedElement) => void;
  onHover: (sel: SelectedElement) => void;
}

function configLabel(phase: PhaseMeasurement): string {
  const parts: string[] = [];
  if (phase.name) parts.push(phase.name);
  if (phase.struct && phase.struct !== phase.name) parts.push(phase.struct);
  const tags = phase.tags?.join(", ");
  if (tags && tags !== phase.name && tags !== phase.struct) parts.push(tags);
  return parts.length > 0 ? parts.join(", ") : "phase";
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n) + "\u2026" : s;
}

export default function ConfigGraphViewer({
  experiment,
  onSelect,
  onHover,
}: ConfigGraphViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const onSelectRef = useRef(onSelect);
  const onHoverRef = useRef(onHover);

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);
  useEffect(() => { onHoverRef.current = onHover; }, [onHover]);

  useEffect(() => {
    if (!containerRef.current || !experiment) return;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const elements: any[] = [];

    for (const node of experiment.nodes) {
      const phases = (node.measurements ?? []).filter(
        (m): m is PhaseMeasurement => m.type === "phase"
      );
      if (phases.length === 0) continue;

      // Add material node
      const materialId = `material-${node.id}`;
      elements.push({
        group: "nodes",
        data: {
          id: materialId,
          label: truncate(node.label, 30),
          fullLabel: node.label,
          nodeType: "material",
          materialNodeData: node,
        },
      });

      // Build a map of phase name -> phase for within lookups
      const phaseByName = new Map<string, PhaseMeasurement>();
      for (const p of phases) {
        if (p.name) phaseByName.set(p.name, p);
      }

      // Add config nodes and edges
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
            phase,
            materialNodeData: node,
          },
        });

        // Connect: if within is set and refers to a known phase, connect to parent config
        if (phase.within && phaseByName.has(phase.within)) {
          const parentIdx = phases.indexOf(phaseByName.get(phase.within)!);
          const parentId = `config-${node.id}-${parentIdx}`;
          elements.push({
            group: "edges",
            data: {
              id: `${parentId}->${configId}`,
              source: parentId,
              target: configId,
            },
          });
        } else {
          // Root-level config — connect to material
          elements.push({
            group: "edges",
            data: {
              id: `${materialId}->${configId}`,
              source: materialId,
              target: configId,
            },
          });
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
            "background-color": "#8957e5",
            "border-width": 2,
            "border-color": "#a371f7",
            "text-outline-color": "#8957e5",
            "text-outline-width": 1,
          },
        },
        {
          selector: 'node[nodeType="material"]',
          style: {
            "background-color": "#1f6feb",
            "border-color": "#388bfd",
            "text-outline-color": "#1f6feb",
          },
        },
        {
          selector: 'node[nodeType="config"]',
          style: {
            "background-color": "#8957e5",
            "border-color": "#a371f7",
            "text-outline-color": "#8957e5",
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
            "curve-style": "bezier",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#30363d",
            "line-color": "#30363d",
            width: 2,
          },
        },
        {
          selector: "edge.hover",
          style: {
            "line-color": "#58a6ff",
            "target-arrow-color": "#58a6ff",
            width: 3,
          },
        },
        {
          selector: "edge.selected",
          style: {
            "line-color": "#58a6ff",
            "target-arrow-color": "#58a6ff",
            width: 3,
          },
        },
      ],
      layout: {
        name: "dagre",
        rankDir: "TB",
        nodeSep: 60,
        rankSep: 80,
        edgeSep: 30,
        padding: 40,
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
      } as any,
      minZoom: 0.2,
      maxZoom: 4,
    });

    cyRef.current = cy;

    // Node hover
    cy.on("mouseover", "node", (e) => {
      const n = e.target;
      n.addClass("hover");
      const d = n.data();
      const materialData = d.materialNodeData;
      onHoverRef.current({
        kind: "node",
        data: {
          id: materialData.id,
          type: materialData.type,
          label: materialData.label,
          name: materialData.name,
          measurements: materialData.measurements,
          materials: materialData.materials,
          source_code: materialData.source_code,
          start_line: materialData.start_line,
          end_line: materialData.end_line,
        },
      });
    });
    cy.on("mouseout", "node", (e) => {
      e.target.removeClass("hover");
      onHoverRef.current(null);
    });

    // Node click
    cy.on("tap", "node", (e) => {
      cy.edges().removeClass("selected");
      const d = e.target.data();
      const materialData = d.materialNodeData;
      onSelectRef.current({
        kind: "node",
        data: {
          id: materialData.id,
          type: materialData.type,
          label: materialData.label,
          name: materialData.name,
          measurements: materialData.measurements,
          materials: materialData.materials,
          source_code: materialData.source_code,
          start_line: materialData.start_line,
          end_line: materialData.end_line,
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
  }, [experiment]);

  return (
    <div ref={containerRef} className="relative h-full w-full bg-[#0d1117]" />
  );
}
