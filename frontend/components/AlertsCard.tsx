"use client";
import { useEffect, useState } from "react";
import { apiGet, type Alerts } from "@/lib/api";

export default function AlertsCard() {
  const [data, setData] = useState<Alerts | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    apiGet<Alerts>("/alerts").then(setData).catch(() => setFailed(true));
  }, []);
  return (
    <section aria-labelledby="al" className="rounded border border-line p-4">
      <h2 id="al" className="text-lg font-semibold">Service alerts</h2>
      {failed && <p className="mt-2 text-sm text-warn"><span aria-hidden="true">✕</span> Alerts unavailable (backend offline).</p>}
      {data && data.alerts.length === 0 && <p className="mt-2 text-sm"><span aria-hidden="true">✓</span> No service alerts for your shuttle routes.</p>}
      {data && data.alerts.length > 0 && (
        <ul className="mt-2 space-y-2 text-sm">
          {data.alerts.map((a, i) => (
            <li key={i}>
              <span aria-hidden="true">⚠</span> <span className="sr-only">Alert: </span>{a.text}
              <div className="text-xs opacity-70">Why: {a.why}</div>
            </li>
          ))}
        </ul>
      )}
      {data?.notes.map((n) => <p key={n} className="mt-1 text-xs opacity-70">{n}</p>)}
      {data && <p className="mt-2 text-xs opacity-60">{data.note_no_route_alerts}</p>}
    </section>
  );
}
