"use client";

import { useEffect, useState, useCallback } from "react";
import Header from "@/components/Header";
import PaperList from "@/components/PaperList";
import GraphViewer from "@/components/GraphViewer";
import DetailsSidebar from "@/components/DetailsSidebar";
import DescriptionsPanel from "@/components/DescriptionsPanel";
import { GraphData, SelectedElement } from "@/types/graph";

export default function Home() {
  const [graphData, setGraphData] = useState<GraphData>({});
  const [currentDoi, setCurrentDoi] = useState<string | null>(null);
  const [currentExpIdx, setCurrentExpIdx] = useState(0);
  const [selected, setSelected] = useState<SelectedElement>(null);
  const [hovered, setHovered] = useState<SelectedElement>(null);
  const [view, setView] = useState<"graph" | "descriptions">("graph");

  useEffect(() => {
    const controller = new AbortController();
    const dataUrl =
      (process.env.NEXT_PUBLIC_BASE_PATH ?? "") + "/data/litxalloy_graph.json";
    fetch(dataUrl, { signal: controller.signal })
      .then((r) => r.json())
      .then((data: GraphData) => {
        setGraphData(data);
        const dois = Object.keys(data);
        if (dois.length > 0) {
          setCurrentDoi(dois[0]);
          setCurrentExpIdx(0);
        }
      })
      .catch((err) => {
        if (err.name !== "AbortError") console.error("Failed to fetch graph:", err);
      });
    return () => controller.abort();
  }, []);

  const handleSelectPaper = useCallback((doi: string, expIdx: number) => {
    setCurrentDoi(doi);
    setCurrentExpIdx(expIdx);
    setSelected(null);
    setHovered(null);
  }, []);

  const handleSelect = useCallback((sel: SelectedElement) => {
    setSelected(sel);
  }, []);

  const handleHover = useCallback((sel: SelectedElement) => {
    setHovered(sel);
  }, []);

  const experiment =
    currentDoi && graphData[currentDoi]
      ? graphData[currentDoi][currentExpIdx] ?? null
      : null;

  return (
    <div className="grid h-screen grid-cols-[320px_1fr_360px] grid-rows-[auto_1fr]">
      <Header
        graphData={graphData}
        currentDoi={currentDoi}
        currentExpIdx={currentExpIdx}
        nodeCount={experiment?.nodes.length ?? 0}
        edgeCount={experiment?.edges.length ?? 0}
        view={view}
        onSelectPaper={handleSelectPaper}
        onViewChange={setView}
      />
      <PaperList
        graphData={graphData}
        currentDoi={currentDoi}
        onSelectPaper={handleSelectPaper}
      />
      {view === "graph" ? (
        <>
          <GraphViewer experiment={experiment} onSelect={handleSelect} onHover={handleHover} />
          <DetailsSidebar selected={hovered ?? selected} />
        </>
      ) : (
        <div className="col-span-2">
          <DescriptionsPanel descriptions={experiment?.descriptions ?? []} />
        </div>
      )}
    </div>
  );
}
