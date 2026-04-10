"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import GraphViewer from "@/components/GraphViewer";
import DetailsSidebar from "@/components/DetailsSidebar";
import { Experiment, SelectedElement } from "@/types/graph";

const isStatic = process.env.NEXT_PUBLIC_STATIC_EXPORT === "true";

function SetupInstructions() {
  return (
    <div className="flex h-screen flex-col bg-[#0d1117] text-[#e6edf3]">
      <header className="flex items-center gap-4 border-b border-[#30363d] bg-[#161b22] px-5 py-3">
        <Link href="/" className="text-[#58a6ff] hover:underline text-sm">
          &larr; Graph Viewer
        </Link>
        <h1 className="text-base font-semibold">Transcribe &amp; Extract</h1>
      </header>
      <div className="flex flex-1 items-center justify-center px-4">
        <div className="text-center max-w-md">
          <h2 className="text-xl font-semibold text-[#e6edf3] mb-2">
            Run Transcribe Locally
          </h2>
          <p className="text-sm text-[#8b949e] mb-6">
            The transcribe feature processes PDFs using OCR and LLM extraction. It requires a local server with API keys configured.
          </p>
          <a
            href="https://github.com/Radical-AI/litxbench/blob/main/docs/transcribe.md"
            className="inline-block rounded-md bg-[#1f6feb] px-5 py-2.5 text-sm font-medium text-white hover:bg-[#388bfd] transition-colors"
          >
            View setup instructions
          </a>
        </div>
      </div>
    </div>
  );
}

interface LogEntry {
  id: number;
  event: string;
  message: string;
  step?: string;
}

const MAX_LOGS = 500;

export default function TranscribePage() {
  if (isStatic) return <SetupInstructions />;
  return <InteractiveTranscribe />;
}

function AlloysOnlyBanner() {
  return (
    <div className="border-b border-[#d29922]/30 bg-[#d29922]/10 px-5 py-2 text-xs text-[#d29922]">
      <strong>Note:</strong> LitXBench transcription is currently optimized specifically for extracting experiments from alloy papers.
    </div>
  );
}

function InteractiveTranscribe() {
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [experiments, setExperiments] = useState<Experiment[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<SelectedElement>(null);
  const [hovered, setHovered] = useState<SelectedElement>(null);
  const [currentExpIdx, setCurrentExpIdx] = useState(0);
  const logIdRef = useRef(0);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Abort any in-flight request when unmounting
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const addLog = useCallback((entry: Omit<LogEntry, "id">) => {
    const newEntry = { ...entry, id: logIdRef.current++ };
    setLogs((prev) => {
      const next = [...prev, newEntry];
      return next.length > MAX_LOGS ? next.slice(-MAX_LOGS) : next;
    });
    setTimeout(() => logsEndRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);

  const startProcessing = useCallback(
    async (f: File) => {
      if (isProcessing) return;
      setFile(f);
      setIsProcessing(true);
      setError(null);
      setLogs([]);
      setExperiments(null);
      setCurrentStep("uploading");
      setSelected(null);
      setHovered(null);
      setCurrentExpIdx(0);
      addLog({ event: "status", message: `Uploading ${f.name}...` });

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const formData = new FormData();
      formData.append("pdf", f);

      try {
        const response = await fetch("/api/transcribe", {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        if (!response.ok || !response.body) {
          setError(`Upload failed: ${response.statusText}`);
          setIsProcessing(false);
          setCurrentStep(null);
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (!line.trim()) continue;
              try {
                const data = JSON.parse(line);
                if (data.event === "status") {
                  setCurrentStep(data.step || null);
                  addLog({ event: "status", message: data.message, step: data.step });
                } else if (data.event === "error") {
                  addLog({ event: "error", message: data.message, step: data.step });
                  setError(data.message);
                } else if (data.event === "result") {
                  setExperiments(data.experiments);
                  addLog({
                    event: "result",
                    message: `Extracted ${data.experiments?.length ?? 0} experiments`,
                  });
                } else if (data.event === "log") {
                  addLog({ event: "log", message: data.message });
                } else if (data.event === "done") {
                  if (data.exitCode === 0) {
                    addLog({ event: "status", message: "Pipeline complete." });
                  }
                }
              } catch {
                addLog({ event: "log", message: line });
              }
            }
          }
        } finally {
          reader.releaseLock();
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") return;
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setIsProcessing(false);
        setCurrentStep(null);
        abortRef.current = null;
      }
    },
    [isProcessing, addLog]
  );

  const handleFile = useCallback(
    (f: File) => {
      if (f.type !== "application/pdf") {
        setError("Please upload a PDF file.");
        return;
      }
      startProcessing(f);
    },
    [startProcessing]
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!isProcessing) setIsDragging(true);
    },
    [isProcessing]
  );

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      if (isProcessing) return;
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile) handleFile(droppedFile);
    },
    [isProcessing, handleFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selected = e.target.files?.[0];
      if (selected) handleFile(selected);
    },
    [handleFile]
  );

  const stepLabel = currentStep === "uploading" ? "Uploading..." : currentStep === "ocr" ? "Running OCR..." : currentStep === "extraction" ? "Extracting experiments..." : "Processing...";

  const resetToUpload = useCallback(() => {
    abortRef.current?.abort();
    setFile(null);
    setIsProcessing(false);
    setError(null);
    setLogs([]);
    setExperiments(null);
    setCurrentStep(null);
    setSelected(null);
    setHovered(null);
    setCurrentExpIdx(0);
  }, []);

  // --- Idle: full-screen drop zone ---
  if (!file && !isProcessing && !experiments) {
    return (
      <div className="flex h-screen flex-col bg-[#0d1117] text-[#e6edf3]">
        <header className="flex items-center gap-4 border-b border-[#30363d] bg-[#161b22] px-5 py-3">
          <Link href="/" className="text-[#58a6ff] hover:underline text-sm">
            &larr; Graph Viewer
          </Link>
          <h1 className="text-base font-semibold">Transcribe &amp; Extract</h1>
        </header>
        <AlloysOnlyBanner />
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => document.getElementById("pdf-input")?.click()}
          className={`flex flex-1 cursor-pointer flex-col items-center justify-center transition-colors ${
            isDragging ? "bg-[#58a6ff]/10" : ""
          }`}
        >
          <input
            id="pdf-input"
            type="file"
            accept="application/pdf"
            className="hidden"
            onChange={handleFileInput}
          />
          <svg
            className={`mb-4 h-16 w-16 ${isDragging ? "text-[#58a6ff]" : "text-[#30363d]"}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
            />
          </svg>
          <p className="text-sm text-[#c9d1d9]">Drop a PDF here to transcribe &amp; extract</p>
          <p className="mt-1 text-xs text-[#484f58]">or click to browse</p>
          {error && (
            <div className="mt-6 rounded-md border border-[#f85149]/30 bg-[#f85149]/10 px-4 py-3 text-sm text-[#f85149]">
              {error}
            </div>
          )}
        </div>
      </div>
    );
  }

  // --- Processing: full-screen logs ---
  if (isProcessing && !experiments) {
    return (
      <div className="flex h-screen flex-col bg-[#0d1117] text-[#e6edf3]">
        <header className="flex items-center gap-4 border-b border-[#30363d] bg-[#161b22] px-5 py-3">
          <Link href="/" className="text-[#58a6ff] hover:underline text-sm">
            &larr; Graph Viewer
          </Link>
          <h1 className="text-base font-semibold">Transcribe &amp; Extract</h1>
          <span className="text-xs text-[#8b949e]">{file?.name}</span>
          <span className="ml-auto flex items-center gap-2 text-xs text-[#58a6ff]">
            <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-[#58a6ff]" />
            {stepLabel}
          </span>
        </header>
        <AlloysOnlyBanner />
        <div className="flex-1 overflow-y-auto p-4 font-mono text-xs">
          {logs.map((log) => (
            <div
              key={log.id}
              className={`py-0.5 ${
                log.event === "error"
                  ? "text-[#f85149]"
                  : log.event === "result"
                    ? "text-[#3fb950]"
                    : log.event === "log"
                      ? "text-[#6e7681]"
                      : "text-[#c9d1d9]"
              }`}
            >
              {log.step && (
                <span className="mr-2 rounded bg-[#30363d] px-1.5 py-0.5 text-[10px] uppercase text-[#8b949e]">
                  {log.step}
                </span>
              )}
              {log.message}
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
        {error && (
          <div className="border-t border-[#30363d] px-4 py-3 text-sm text-[#f85149]">
            {error}
          </div>
        )}
      </div>
    );
  }

  // --- Error: processing failed without producing experiments ---
  if (error && !experiments) {
    return (
      <div className="flex h-screen flex-col bg-[#0d1117] text-[#e6edf3]">
        <header className="flex items-center gap-4 border-b border-[#30363d] bg-[#161b22] px-5 py-3">
          <Link href="/" className="text-[#58a6ff] hover:underline text-sm">
            &larr; Graph Viewer
          </Link>
          <h1 className="text-base font-semibold">Transcribe &amp; Extract</h1>
          <span className="text-xs text-[#8b949e]">{file?.name}</span>
        </header>
        <AlloysOnlyBanner />
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex flex-col items-center justify-center gap-4 px-4 py-12">
            <div className="rounded-md border border-[#f85149]/30 bg-[#f85149]/10 px-6 py-4 max-w-xl w-full">
              <p className="text-sm font-medium text-[#f85149] mb-1">Error</p>
              <p className="text-sm text-[#f85149]/90">{error}</p>
            </div>
            <button
              onClick={resetToUpload}
              className="cursor-pointer rounded-md border border-[#30363d] bg-[#21262d] px-4 py-2 text-sm text-[#c9d1d9] hover:border-[#484f58] hover:text-white transition-colors"
            >
              Try another PDF
            </button>
          </div>
          {logs.length > 0 && (
            <details className="border-t border-[#30363d]" open>
              <summary className="cursor-pointer select-none px-4 py-2 text-xs font-medium text-[#8b949e] hover:text-[#c9d1d9]">
                Logs ({logs.length})
              </summary>
              <div className="max-h-[300px] overflow-y-auto px-4 pb-2 font-mono text-xs">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className={`py-0.5 ${
                      log.event === "error"
                        ? "text-[#f85149]"
                        : log.event === "result"
                          ? "text-[#3fb950]"
                          : log.event === "log"
                            ? "text-[#6e7681]"
                            : "text-[#c9d1d9]"
                    }`}
                  >
                    {log.step && (
                      <span className="mr-2 rounded bg-[#30363d] px-1.5 py-0.5 text-[10px] uppercase text-[#8b949e]">
                        {log.step}
                      </span>
                    )}
                    {log.message}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>
    );
  }

  // --- Results: graph + sidebar ---
  return (
    <div className="flex h-screen flex-col bg-[#0d1117] text-[#e6edf3]">
      <header className="flex items-center gap-4 border-b border-[#30363d] bg-[#161b22] px-5 py-3">
        <Link href="/" className="text-[#58a6ff] hover:underline text-sm">
          &larr; Graph Viewer
        </Link>
        <h1 className="text-base font-semibold">Transcribe &amp; Extract</h1>
        <span className="text-xs text-[#8b949e]">{file?.name}</span>
        {experiments && (
          <span className="text-xs text-[#3fb950]">
            {experiments.length} experiment{experiments.length !== 1 ? "s" : ""}
          </span>
        )}
        <button
          onClick={resetToUpload}
          className="ml-auto cursor-pointer rounded-md border border-[#30363d] bg-[#21262d] px-3 py-1 text-xs text-[#c9d1d9] hover:border-[#484f58] hover:text-white transition-colors"
        >
          New PDF
        </button>
      </header>
      <AlloysOnlyBanner />

      <div className="flex flex-1 overflow-hidden">
        {/* Center: Graph + logs */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Experiment tabs */}
          {experiments && experiments.length > 1 && (
            <div className="flex items-center gap-1 border-b border-[#30363d] px-4 py-2">
              {experiments.map((_, i) => (
                <button
                  key={i}
                  onClick={() => {
                    setCurrentExpIdx(i);
                    setSelected(null);
                    setHovered(null);
                  }}
                  className={`cursor-pointer rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                    i === currentExpIdx
                      ? "bg-[#1f6feb] text-white"
                      : "text-[#8b949e] hover:bg-[#21262d] hover:text-[#c9d1d9]"
                  }`}
                >
                  Experiment {i + 1}
                </button>
              ))}
            </div>
          )}

          {/* Graph viewer */}
          <div className="flex-1 overflow-hidden">
            <GraphViewer
              experiment={experiments?.[currentExpIdx] ?? null}
              onSelect={setSelected}
              onHover={setHovered}
            />
          </div>

          {/* Collapsible logs */}
          <details className="border-t border-[#30363d]">
            <summary className="cursor-pointer select-none px-4 py-2 text-xs font-medium text-[#8b949e] hover:text-[#c9d1d9]">
              Logs ({logs.length})
            </summary>
            <div className="max-h-[200px] overflow-y-auto px-4 pb-2 font-mono text-xs">
              {logs.map((log) => (
                <div
                  key={log.id}
                  className={`py-0.5 ${
                    log.event === "error"
                      ? "text-[#f85149]"
                      : log.event === "result"
                        ? "text-[#3fb950]"
                        : log.event === "log"
                          ? "text-[#6e7681]"
                          : "text-[#c9d1d9]"
                  }`}
                >
                  {log.step && (
                    <span className="mr-2 rounded bg-[#30363d] px-1.5 py-0.5 text-[10px] uppercase text-[#8b949e]">
                      {log.step}
                    </span>
                  )}
                  {log.message}
                </div>
              ))}
              <div ref={logsEndRef} />
            </div>
          </details>
        </div>

        {/* Right: Details sidebar */}
        <div className="w-[360px] shrink-0">
          <DetailsSidebar selected={hovered ?? selected} />
        </div>
      </div>
    </div>
  );
}
