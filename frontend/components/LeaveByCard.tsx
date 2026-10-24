"use client";
import { useEffect, useState } from "react";
import { apiGet, type LeaveBy, type Schedule, type Section } from "@/lib/api";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));

/** Next upcoming meeting (browser local time) among timed sections. */
function nextClass(sections: Section[], now = new Date()): { id: string; day: string } | null {
  const today = (now.getDay() + 6) % 7; // Mon=0
  const nowMin = now.getHours() * 60 + now.getMinutes();
  let best: { id: string; day: string; at: number } | null = null;
  for (const s of sections) {
    if (!s.start || !s.days.length) continue;
    for (const d of s.days) {
      let delta = (DAYS.indexOf(d) - today + 7) % 7;
      if (delta === 0 && mins(s.start) <= nowMin) delta = 7;
      const at = delta * 1440 + mins(s.start) - nowMin;
      if (!best || at < best.at) best = { id: s.id, day: d, at };
    }
  }
  return best && { id: best.id, day: best.day };
}

export default function LeaveByCard({ schedule }: { schedule: Schedule }) {
  const [data, setData] = useState<LeaveBy | null>(null);
  const [error, setError] = useState("");
  const [tick, setTick] = useState(0); // bump to refresh
  const [done, setDone] = useState(-1);
  const busy = done !== tick;

  useEffect(() => {
    const next = nextClass(schedule.sections);
    let live = true;
    const finish = () => live && setDone(tick);
    if (!next) {
      Promise.resolve().then(() => live && (setError("This schedule has no classes with fixed times."), finish()));
      return () => void (live = false);
    }
    apiGet<LeaveBy>(`/leave-by?schedule_id=${schedule.id}&class_id=${encodeURIComponent(next.id)}&day=${next.day}`)
      .then((d) => live && (setData(d), setError("")))
      .catch(() => live && (setData(null), setError("Could not compute a leave-by time. The backend may be offline, or this schedule needs to be generated again.")))
      .finally(finish);
    return () => void (live = false);
  }, [schedule, tick]);

  return (
    <section aria-labelledby="lb" className="rounded border border-line p-4">
      <div className="flex items-center justify-between gap-2">
        <h2 id="lb" className="text-lg font-semibold">Leave-by: next class</h2>
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
          <p className="text-3xl font-bold">
            <span aria-hidden="true">{data.mode === "bus" ? "🚌" : "🚶"}</span> Leave by {data.leave_at}
            <span className="ml-2 text-base font-normal opacity-80">{data.mode === "bus" ? "(shuttle bus)" : "(walk)"}</span>
          </p>
          <p className="text-sm font-medium">
            <span aria-hidden="true">{data.probability_on_time >= 0.85 ? "✓" : data.probability_on_time >= 0.5 ? "▲" : "✕"}</span>{" "}
            {data.probability_label} chance of arriving on time
          </p>
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
