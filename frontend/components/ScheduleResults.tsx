import type { GenerateResult, Schedule } from "@/lib/api";
import ScheduleGrid from "./ScheduleGrid";

const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));

export default function ScheduleResults({ result, selectedId, onUse }: { result: GenerateResult; selectedId?: string; onUse: (s: Schedule) => void }) {
  if (result.status === "infeasible") {
    return (
      <div role="alert" className="rounded border border-warn p-3 text-sm">
        <span aria-hidden="true">⚠</span> No valid schedule. {result.reason}
      </div>
    );
  }
  const times = result.schedules.flatMap((s) => s.sections).filter((s) => s.start && s.end);
  const from = Math.min(8, ...times.map((s) => Math.floor(mins(s.start!) / 60)));
  const to = Math.max(18, ...times.map((s) => Math.ceil(mins(s.end!) / 60)));

  return (
    <div className="space-y-6">
      <p className="text-xs opacity-80"><span aria-hidden="true">◆</span> {result.label}. Fictional courses; results are illustrative.</p>
      {result.warnings.map((w) => (
        <p key={w} className="text-sm text-warn"><span aria-hidden="true">⚠</span> {w}</p>
      ))}
      {result.note && <p className="text-sm"><span aria-hidden="true">ℹ</span> {result.note}</p>}
      {result.schedules.map((s) => {
        const m = s.metrics;
        return (
          <article key={s.rank} aria-labelledby={`s${s.rank}`} className="rounded border border-line p-4">
            <h3 id={`s${s.rank}`} className="text-lg font-semibold">
              Schedule {s.rank} <span className="text-sm font-normal opacity-70">· {s.credits} credits{s.optimal ? "" : " · best found in time limit"}</span>
            </h3>
            <p className="text-sm opacity-80">{s.courses.map((c) => c.code).join(", ")}</p>
            <button type="button" onClick={() => onUse(s)} aria-pressed={selectedId === s.id} className="mt-2 rounded border border-accent px-3 py-1 text-sm font-medium text-accent">
              {selectedId === s.id ? "✓ Using this schedule (see Week tab)" : "Use this schedule"}
            </button>
            <dl className="my-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
              <div className="rounded bg-surface p-2">
                <dt className="opacity-70">Tight transitions</dt>
                <dd className="font-semibold">{m.tight_transitions === 0 ? <><span aria-hidden="true">✓</span> 0</> : <><span aria-hidden="true">⚠</span> {m.tight_transitions}</>}</dd>
              </div>
              <div className="rounded bg-surface p-2">
                <dt className="opacity-70">Walking per week</dt>
                <dd className="font-semibold">≈ {m.travel_minutes_range[0]}–{m.travel_minutes_range[1]} min</dd>
              </div>
              <div className="rounded bg-surface p-2">
                <dt className="opacity-70">Lunch-window days</dt>
                <dd className="font-semibold">{m.meal_window_days === m.class_days ? <span aria-hidden="true">✓ </span> : <span aria-hidden="true">⚠ </span>}{m.meal_window_days} of {m.class_days}</dd>
              </div>
              <div className="rounded bg-surface p-2">
                <dt className="opacity-70">Longest gap</dt>
                <dd className="font-semibold">{m.longest_gap_minutes} min</dd>
              </div>
            </dl>
            <p className="mb-3 text-sm">{s.explanation}</p>
            {s.flags.length > 0 && (
              <ul className="mb-3 space-y-1 text-sm">
                {s.flags.map((f, i) => (
                  <li key={i}>
                    <span aria-hidden="true">{f.level === "warn" ? "⚠" : "ℹ"}</span>{" "}
                    <span className="sr-only">{f.level === "warn" ? "Warning:" : "Note:"}</span>
                    {f.why}
                  </li>
                ))}
              </ul>
            )}
            <ScheduleGrid schedule={s} from={from} to={to} />
          </article>
        );
      })}
    </div>
  );
}
