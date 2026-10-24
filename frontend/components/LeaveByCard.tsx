"use client";
import { useEffect, useState } from "react";
import { apiGet, type LeaveBy, type Schedule } from "@/lib/api";
import { nextClass } from "@/lib/schedule";

export default function LeaveByCard({ schedule, todayOnly = false, title }: { schedule: Schedule; todayOnly?: boolean; title?: string }) {
  const [data, setData] = useState<LeaveBy | null>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0); // bump to refresh
  const [done, setDone] = useState(-1);
  const busy = done !== tick;

  useEffect(() => {
    const next = nextClass(schedule.sections, new Date(), todayOnly);
    let live = true;
    const finish = () => live && setDone(tick);
    if (!next) {
      Promise.resolve().then(() => live && (setError(todayOnly ? "No more classes to leave for today." : "This schedule has no classes with fixed times."), finish()));
      return () => void (live = false);
    }
    apiGet<LeaveBy>(`/leave-by?schedule_id=${schedule.id}&class_id=${encodeURIComponent(next.id)}&day=${next.day}`)
      .then((d) => live && (setData(d), setError("")))
      .catch(() => live && (setData(null), setError("Could not compute a leave-by time. The backend may be offline, or this schedule needs to be generated again.")))
      .finally(finish);
    return () => void (live = false);
  }, [schedule, tick, todayOnly]);

  return (
    <section aria-labelledby="lb" className="rounded border border-line p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 id="lb" className="text-lg font-semibold">{title ?? "Leave-by: next class"}</h2>
        <button type="button" onClick={() => setTick((n) => n + 1)} disabled={busy} className="rounded border border-line bg-surface px-2 py-1 text-sm">
          <span aria-hidden="true">↻</span> {busy ? "Updating…" : "Refresh"}
        </button>
      </div>
      {error && <p role="alert" className="mt-2 text-sm text-warn"><span aria-hidden="true">⚠</span> {error}</p>}
      {data && (
        <div className="mt-2 space-y-2">
          <p className="text-sm opacity-80">
            {data.course_code} · {data.day} {new Date(data.class_start).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", timeZone: "America/New_York" })} · {data.destination}
          </p>
          {data.mode === "unknown" || data.leave_at === null ? (
            <p className="text-2xl font-bold">
              <span aria-hidden="true">? </span>Location unknown
              <span className="block text-sm font-normal opacity-80">No walking time, so no leave-by time or on-time chance.</span>
            </p>
          ) : (
            <>
              <p className="text-3xl font-bold">
                <span aria-hidden="true">{data.mode === "bus" ? "🚌" : "🚶"}</span> Leave by {data.leave_at}
                <span className="ml-2 text-base font-normal opacity-80">{data.mode === "bus" ? "(shuttle bus)" : "(walk)"}{data.approximate ? " · approximate ≈" : ""}</span>
              </p>
              <p className="text-sm font-medium">
                <span aria-hidden="true">{(data.probability_on_time ?? 0) >= 0.85 ? "✓" : (data.probability_on_time ?? 0) >= 0.5 ? "▲" : "✕"}</span>{" "}
                {data.probability_label} chance of arriving on time
              </p>
            </>
          )}
          <p className="text-sm"><span className="font-medium">Why: </span>{data.why}</p>
          {data.delay_model?.synthetic && (
            <p className="text-xs text-warn"><span aria-hidden="true">⚠</span> Bus delay estimates use synthetic placeholder data until enough real predictions are logged.</p>
          )}
          {data.warnings.map((w) => (
            <p key={w} className="text-sm text-warn"><span aria-hidden="true">⚠</span> {w}</p>
          ))}
        </div>
      )}
    </section>
  );
}
