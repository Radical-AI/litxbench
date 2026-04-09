"use client";

import { Measurement } from "@/types/graph";

function formatKind(kind: string | undefined | null): string {
  if (!kind) return "";
  return kind
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const TYPE_COLORS: Record<string, string> = {
  composition: "text-[#a5d6ff]",
  measurement: "text-[#7ee787]",
  phase: "text-[#d2a8ff]",
  global_lattice_param: "text-[#ffa657]",
  lattice: "text-[#f0883e]",
};

function SourceLine({ source }: { source: string }) {
  return (
    <details className="mt-1">
      <summary className="cursor-pointer text-[11px] text-[#8b949e] select-none">
        Source
      </summary>
      <div className="mt-0.5 text-[11px] text-[#8b949e]">{source}</div>
    </details>
  );
}

export default function MeasurementCard({ m }: { m: Measurement }) {
  const colorClass = TYPE_COLORS[m.type] ?? "text-[#8b949e]";

  return (
    <div className="mb-2 rounded-md border border-[#30363d] bg-[#0d1117] p-2.5">
      {m.type === "composition" && (
        <>
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${colorClass}`}>
            Composition
          </div>
          <div className="text-[13px] font-medium text-[#e6edf3]">
            {m.formula}
          </div>
          {m.method && (
            <div className="mt-1 text-[11px] text-[#8b949e]">Method: {m.method}</div>
          )}
          {m.description && (
            <div className="mt-1 text-[11px] text-[#8b949e]">{m.description}</div>
          )}
          {m.source && <SourceLine source={m.source} />}
        </>
      )}

      {m.type === "measurement" && (
        <>
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${colorClass}`}>
            Measurement
          </div>
          <div className="text-[13px] font-medium text-[#e6edf3]">
            {formatKind(m.kind)}
          </div>
          <div className="my-0.5 text-lg font-bold text-[#e6edf3]">
            {m.value}
            {m.uncertainty != null && ` \u00b1 ${m.uncertainty}`}
          </div>
          {m.unit && (
            <div className="text-xs text-[#8b949e]">{m.unit}</div>
          )}
          {m.measurement_method && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              Method: {m.measurement_method}
            </div>
          )}
          {m.measurement_statistic && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              Statistic: {m.measurement_statistic}
            </div>
          )}
          {m.temperature && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              T: {m.temperature}
            </div>
          )}
          {m.pressure && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              P: {m.pressure}
            </div>
          )}
          {m.description && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              {m.description}
            </div>
          )}
          {m.source && <SourceLine source={m.source} />}
        </>
      )}

      {m.type === "phase" && (
        <>
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${colorClass}`}>
            Phase
          </div>
          <div className="text-[13px] font-medium text-[#e6edf3]">
            {m.struct ?? m.name ?? "Unknown"}
            {m.name && m.struct && (
              <span className="ml-1 text-[11px] text-[#8b949e]">({m.name})</span>
            )}
          </div>
          {m.tags && m.tags.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {m.tags.map((tag, i) => (
                <span key={i} className="rounded bg-[#1c2128] px-1.5 py-0.5 text-[10px] text-[#8b949e]">
                  {tag}
                </span>
              ))}
            </div>
          )}
          {m.within && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              Within: {m.within}
            </div>
          )}
          {m.description && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              {m.description}
            </div>
          )}
          {m.source && <SourceLine source={m.source} />}
          {m.measurements && m.measurements.length > 0 && (
            <div className="ml-2 mt-1.5">
              {m.measurements.map((nested, i) => (
                <MeasurementCard key={i} m={nested} />
              ))}
            </div>
          )}
        </>
      )}

      {m.type === "global_lattice_param" && (
        <>
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${colorClass}`}>
            Global Lattice Param
          </div>
          <div className="text-[13px] font-medium text-[#e6edf3]">
            {m.struct ?? m.name ?? "Unknown"}
            {m.name && m.struct && (
              <span className="ml-1 text-[11px] text-[#8b949e]">({m.name})</span>
            )}
          </div>
          {m.phase_fraction && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              Phase fraction: {m.phase_fraction}
            </div>
          )}
          {m.lattice_description && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              {m.lattice_description}
            </div>
          )}
          {m.description && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              {m.description}
            </div>
          )}
          {m.source && <SourceLine source={m.source} />}
        </>
      )}

      {m.type === "lattice" && (
        <>
          <div className={`text-[10px] font-semibold uppercase tracking-wide ${colorClass}`}>
            Lattice
          </div>
          <div className="text-[13px] font-medium text-[#e6edf3]">
            {m.a != null && m.b != null && m.c != null
              ? `a=${m.a}, b=${m.b}, c=${m.c}`
              : "Lattice parameters"}
          </div>
          {m.description && (
            <div className="mt-1 text-[11px] text-[#8b949e]">
              {m.description}
            </div>
          )}
          {m.source && <SourceLine source={m.source} />}
        </>
      )}
    </div>
  );
}
