"use client";

import { DescriptionGroup } from "@/types/graph";

function formatKind(kind: string): string {
  return kind
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface DescriptionsPanelProps {
  descriptions: DescriptionGroup[];
}

export default function DescriptionsPanel({
  descriptions,
}: DescriptionsPanelProps) {
  if (descriptions.length === 0) {
    return (
      <div className="flex h-full items-center justify-center bg-[#0d1117]">
        <span className="text-[13px] text-[#484f58]">
          No description groups for this experiment
        </span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-[#0d1117] p-6">
      <div className="mx-auto max-w-4xl space-y-4">
        {descriptions.map((d, i) => (
          <div
            key={i}
            className="rounded-lg border border-[#30363d] bg-[#161b22] p-5"
          >
            <div className="flex flex-wrap items-start gap-3">
              {/* Kinds */}
              <div className="flex flex-wrap gap-1.5">
                {d.kinds.map((kind, j) => (
                  <span
                    key={j}
                    className="rounded-md bg-[#0d1117] border border-[#30363d] px-2 py-1 text-xs text-[#79c0ff]"
                  >
                    {formatKind(kind)}
                  </span>
                ))}
              </div>

              {/* Method */}
              {d.method && (
                <span className="ml-auto rounded-md bg-[#0d1117] border border-[#30363d] px-2 py-1 text-xs text-[#7ee787]">
                  {formatKind(d.method)}
                </span>
              )}
            </div>

            {/* Group name */}
            {d.group_name && (
              <div className="mt-3 text-xs text-[#8b949e]">
                <span className="text-[#ffa657]">Group:</span> {d.group_name}
              </div>
            )}

            {/* Description */}
            {d.desc && (
              <div className="mt-3 text-sm leading-relaxed text-[#c9d1d9]">
                {d.desc}
              </div>
            )}

            {/* Source */}
            {d.source && (
              <details className="mt-3">
                <summary className="cursor-pointer text-xs text-[#8b949e] select-none">
                  Source
                </summary>
                <div className="mt-1 text-xs text-[#8b949e]">
                  {d.source}
                </div>
              </details>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
