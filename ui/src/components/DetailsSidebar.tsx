"use client";

import { SelectedElement } from "@/types/graph";
import MeasurementCard from "./MeasurementCard";

interface DetailsSidebarProps {
  selected: SelectedElement;
}

function formatKind(kind: string | undefined | null): string {
  if (!kind) return "";
  return kind
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function lineStr(
  startLine: number | null | undefined,
  endLine: number | null | undefined
): string | null {
  if (!startLine) return null;
  if (endLine && endLine !== startLine) return `${startLine}\u2013${endLine}`;
  return String(startLine);
}

export default function DetailsSidebar({ selected }: DetailsSidebarProps) {
  if (!selected) {
    return (
      <div className="flex items-center justify-center overflow-y-auto border-l border-[#30363d] bg-[#161b22] p-4">
        <span className="text-center text-[13px] text-[#484f58]">
          Click a material node to view details
        </span>
      </div>
    );
  }

  if (selected.kind === "config") {
    const phase = selected.data;
    const label = phase.struct ?? phase.name ?? "Phase";
    return (
      <div className="overflow-y-auto border-l border-[#30363d] bg-[#161b22] p-4">
        <h2 className="mb-1 border-b border-[#30363d] pb-2 text-sm font-semibold text-[#e6edf3]">
          {label}
          {phase.name && phase.struct && (
            <span className="ml-1 text-[11px] font-normal text-[#8b949e]">({phase.name})</span>
          )}
        </h2>
        <div className="mb-4 text-[11px] text-[#8b949e]">
          on {selected.parentLabel}
        </div>

        {/* Attributes */}
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
          Attributes
        </h3>
        <div className="mb-4 space-y-0">
          <Attr label="Type" value="phase" />
          {phase.name && <Attr label="Name" value={phase.name} />}
          {phase.struct && <Attr label="Structure" value={phase.struct} />}
          {phase.within && <Attr label="Within" value={phase.within} />}
        </div>

        {/* Tags */}
        {phase.tags && phase.tags.length > 0 && (
          <>
            <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
              Tags
            </h3>
            <div className="mb-4 flex flex-wrap gap-1">
              {phase.tags.map((tag, i) => (
                <span key={i} className="rounded bg-[#1c2128] px-1.5 py-0.5 text-[10px] text-[#8b949e]">
                  {tag}
                </span>
              ))}
            </div>
          </>
        )}

        {/* Description */}
        {phase.description && (
          <div className="mb-4 text-xs text-[#c9d1d9]">{phase.description}</div>
        )}

        {/* Nested measurements */}
        {phase.measurements && phase.measurements.length > 0 && (
          <>
            <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
              Measurements
            </h3>
            {phase.measurements.map((m, i) => (
              <MeasurementCard key={i} m={m} />
            ))}
          </>
        )}

        {/* Source */}
        {phase.source && (
          <details className="mt-4">
            <summary className="cursor-pointer text-[11px] text-[#8b949e] select-none">
              Source
            </summary>
            <div className="mt-0.5 text-[11px] text-[#8b949e]">{phase.source}</div>
          </details>
        )}
      </div>
    );
  }

  if (selected.kind === "node") {
    const data = selected.data;
    const lines = lineStr(data.start_line, data.end_line);

    return (
      <div className="overflow-y-auto border-l border-[#30363d] bg-[#161b22] p-4">
        <h2 className="mb-3 border-b border-[#30363d] pb-2 text-sm font-semibold text-[#e6edf3]">
          {data.label}
        </h2>

        {/* Measurements */}
        {data.measurements && data.measurements.length > 0 && (
          <>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
              Measurements
            </h3>
            {data.measurements.map((m, i) => (
              <MeasurementCard key={i} m={m} />
            ))}
          </>
        )}

        {/* Materials */}
        {data.materials && (
          <>
            <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
              Materials
            </h3>
            {Object.entries(data.materials).map(([name, mat]) => (
              <div
                key={name}
                className="mb-2 rounded-md border border-[#30363d] bg-[#0d1117] p-2.5"
              >
                <div className="text-[13px] font-semibold text-[#ffa657]">
                  {name}
                </div>
                <div className="text-[11px] text-[#8b949e]">
                  {String(mat.kind)}
                </div>
                {mat.description && (
                  <div className="mt-1 text-xs text-[#c9d1d9]">
                    {mat.description}
                  </div>
                )}
              </div>
            ))}
          </>
        )}

        {/* Source code */}
        {data.source_code && (
          <>
            <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
              Source Code
            </h3>
            <div className="rounded-md border border-[#30363d] bg-[#0d1117] p-2.5">
              <pre className="whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-[#a5d6ff]">
                {data.source_code}
              </pre>
              {lines && (
                <div className="mt-1.5 text-[10px] text-[#484f58]">
                  L{lines}
                </div>
              )}
            </div>
          </>
        )}

        {/* Attributes (Configuration) */}
        <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
          Configuration
        </h3>
        <div className="mb-4 space-y-0">
          <Attr label="Type" value={data.type} />
          {data.name && <Attr label="Name" value={data.name} />}
          <Attr label="ID" value={data.id} small />
          {lines && <Attr label="Lines" value={lines} />}
        </div>
      </div>
    );
  }

  // Edge selected
  const data = selected.data;
  const lines = lineStr(data.start_line, data.end_line);

  return (
    <div className="overflow-y-auto border-l border-[#30363d] bg-[#161b22] p-4">
      <h2 className="mb-3 border-b border-[#30363d] pb-2 text-sm font-semibold text-[#e6edf3]">
        {data.label}
      </h2>

      {/* Endpoints */}
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
        Endpoints
      </h3>
      <div className="mb-2 rounded-md border border-[#30363d] bg-[#0d1117] p-2.5">
        <div className="text-[11px] text-[#8b949e]">
          {data.sourceLabel} &rarr; {data.targetLabel}
        </div>
      </div>

      {/* Process steps */}
      {data.process_steps && data.process_steps.length > 0 && (
        <>
          <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
            Process Steps
          </h3>
          {data.process_steps.map((step, i) => (
            <div
              key={i}
              className="mb-2 rounded-md border border-[#30363d] bg-[#0d1117] p-2.5"
            >
              <div className="text-[10px] font-semibold uppercase tracking-wide text-[#7ee787]">
                Process Step
              </div>
              <div className="text-[13px] font-medium text-[#e6edf3]">
                {formatKind(step.base_name)}
              </div>
              {step.variables &&
                Object.keys(step.variables).length > 0 &&
                Object.entries(step.variables).map(([k, v]) => (
                  <div key={k} className="mt-1 text-[11px] text-[#8b949e]">
                    {k} = {v}
                  </div>
                ))}
              {step.events && step.events.length > 0 && (
                <div className="mt-2 space-y-1.5 border-t border-[#21262d] pt-2">
                  <div className="text-[10px] font-semibold uppercase tracking-wide text-[#d2a8ff]">
                    Events
                  </div>
                  {step.events.map((event, j) => (
                    <div
                      key={j}
                      className="rounded border border-[#21262d] bg-[#161b22] p-2"
                    >
                      <div className="text-[12px] font-medium text-[#e6edf3]">
                        {formatKind(event.kind)}
                      </div>
                      {event.temperature && (
                        <div className="mt-0.5 text-[11px] text-[#8b949e]">
                          Temp: {event.temperature}
                        </div>
                      )}
                      {event.duration && (
                        <div className="mt-0.5 text-[11px] text-[#8b949e]">
                          Duration: {event.duration}
                        </div>
                      )}
                      {event.equipment && (
                        <div className="mt-0.5 text-[11px] text-[#8b949e]">
                          Equipment: {event.equipment}
                        </div>
                      )}
                      {event.inputs && event.inputs.length > 0 && (
                        <div className="mt-0.5 text-[11px] text-[#8b949e]">
                          Inputs: {event.inputs.join(", ")}
                        </div>
                      )}
                      {event.description && (
                        <div className="mt-0.5 text-[11px] text-[#8b949e]">
                          {event.description}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </>
      )}

      {/* Source code */}
      {data.source_code && (
        <>
          <h3 className="mb-2 mt-4 text-xs font-semibold uppercase tracking-wide text-[#8b949e]">
            Source Code
          </h3>
          <div className="rounded-md border border-[#30363d] bg-[#0d1117] p-2.5">
            <pre className="whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-[#a5d6ff]">
              {data.source_code}
            </pre>
            {lines && (
              <div className="mt-1.5 text-[10px] text-[#484f58]">
                L{lines}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function Attr({
  label,
  value,
  small,
}: {
  label: string;
  value: string;
  small?: boolean;
}) {
  return (
    <div className="flex justify-between border-b border-[#21262d] py-1 text-xs last:border-b-0">
      <span className="text-[#8b949e]">{label}</span>
      <span
        className={`font-medium text-[#e6edf3] ${small ? "break-all text-[10px]" : ""}`}
      >
        {value}
      </span>
    </div>
  );
}
