"use client";

import Link from "next/link";
import { GraphData } from "@/types/graph";

interface HeaderProps {
  graphData: GraphData;
  currentDoi: string | null;
  currentExpIdx: number;
  nodeCount: number;
  edgeCount: number;
  view: "graph" | "descriptions";
  onSelectPaper: (doi: string, expIdx: number) => void;
  onViewChange: (view: "graph" | "descriptions") => void;
}

export default function Header({
  graphData,
  currentDoi,
  currentExpIdx,
  nodeCount,
  edgeCount,
  view,
  onSelectPaper,
  onViewChange,
}: HeaderProps) {
  const experiments = currentDoi ? graphData[currentDoi] : [];

  return (
    <header className="col-span-full flex items-center gap-4 border-b border-[#30363d] bg-[#161b22] px-5 py-3">
      <a
        href="/litxbench/"
        className="flex-shrink-0 text-[#8b949e] hover:text-[#58a6ff] transition-colors"
        title="Back to docs"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="currentColor"
        >
          <path
            fillRule="evenodd"
            d="M7.78 12.53a.75.75 0 01-1.06 0L2.47 8.28a.75.75 0 010-1.06l4.25-4.25a.75.75 0 011.06 1.06L4.56 7.25H13a.75.75 0 010 1.5H4.56l3.22 3.22a.75.75 0 010 1.06z"
          />
        </svg>
      </a>
      <h1 className="whitespace-nowrap text-base font-semibold text-[#e6edf3]">
        LitXAlloy Graph Viewer
      </h1>

      {experiments.length > 1 && (
        <div className="ml-2 flex gap-1">
          {experiments.map((_, i) => (
            <button
              key={i}
              onClick={() => currentDoi && onSelectPaper(currentDoi, i)}
              className={`rounded-md border px-2.5 py-1 text-xs cursor-pointer transition-colors ${
                i === currentExpIdx
                  ? "border-[#1f6feb] bg-[#1f6feb] text-white"
                  : "border-[#30363d] bg-[#0d1117] text-[#8b949e] hover:border-[#58a6ff] hover:text-[#c9d1d9]"
              }`}
            >
              Exp {i}
            </button>
          ))}
        </div>
      )}

      <div className="ml-auto flex items-center gap-4">
        <div className="flex rounded-md border border-[#30363d] overflow-hidden">
          <button
            onClick={() => onViewChange("graph")}
            className={`px-3 py-1 text-xs cursor-pointer transition-colors ${
              view === "graph"
                ? "bg-[#1f6feb] text-white"
                : "bg-[#0d1117] text-[#8b949e] hover:text-[#c9d1d9]"
            }`}
          >
            Graph
          </button>
          <button
            onClick={() => onViewChange("descriptions")}
            className={`px-3 py-1 text-xs cursor-pointer transition-colors border-l border-[#30363d] ${
              view === "descriptions"
                ? "bg-[#1f6feb] text-white"
                : "bg-[#0d1117] text-[#8b949e] hover:text-[#c9d1d9]"
            }`}
          >
            Descriptions
          </button>
        </div>
        <span className="whitespace-nowrap text-xs text-[#8b949e]">
          {nodeCount} nodes &middot; {edgeCount} edges
        </span>
        <Link
          href="/transcribe"
          className="rounded-md border border-[#30363d] bg-[#0d1117] px-3 py-1 text-xs text-[#8b949e] hover:border-[#58a6ff] hover:text-[#c9d1d9] transition-colors"
        >
          Transcribe
        </Link>
      </div>
    </header>
  );
}
