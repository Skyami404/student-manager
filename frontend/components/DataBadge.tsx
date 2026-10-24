"use client";
import type { SourceState } from "@/lib/api";
import { useDataStatus } from "@/lib/useDataStatus";

// Every state has an icon AND a text label (never color alone).
const ICON: Record<SourceState, string> = { live: "●", cached: "◐", sample: "◆", unavailable: "✕" };
const WORD: Record<SourceState, string> = { live: "live", cached: "cached", sample: "sample", unavailable: "unavailable" };

function Pill({ children, strong }: { children: React.ReactNode; strong?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        strong ? "border-warn text-warn" : "border-line bg-surface"
      }`}
    >
      {children}
    </span>
  );
}

export default function DataBadge() {
  const { status, offline } = useDataStatus();
  if (offline) {
    return (
      <Pill strong>
        <span aria-hidden="true">✕</span> Backend offline
      </Pill>
    );
  }
  if (!status) return <Pill>Checking data sources…</Pill>;
  return (
    <ul className="flex flex-wrap items-center gap-2" aria-label="Data sources">
      {status.catalog.synthetic ? (
        <li>
          <Pill strong>
            <span aria-hidden="true">⚠</span> Sample catalog (synthetic)
          </Pill>
        </li>
      ) : (
        <li>
          <Pill>
            <span aria-hidden="true">{ICON[status.catalog.status]}</span> Catalog: {WORD[status.catalog.status]}
          </Pill>
        </li>
      )}
      <li>
        <Pill>
          <span aria-hidden="true">{ICON[status.transit.status]}</span> Transit: {WORD[status.transit.status]}
        </Pill>
      </li>
      <li>
        <Pill>
          <span aria-hidden="true">{ICON[status.dining.status]}</span> Dining: {WORD[status.dining.status]}
        </Pill>
      </li>
      {status.delay_model?.synthetic && (
        <li>
          <Pill strong>
            <span aria-hidden="true">⚠</span> Delay model: synthetic data ({status.delay_model.real_trips} real trips logged)
          </Pill>
        </li>
      )}
      {(status.locations.synthetic || status.locations.approximate) && (
        <li>
          <Pill>
            <span aria-hidden="true">◆</span> Locations: approximate ({status.locations.synthetic ? "synthetic" : "unverified"})
          </Pill>
        </li>
      )}
    </ul>
  );
}
