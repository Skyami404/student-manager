import type { Schedule, Section } from "@/lib/api";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
// Okabe-Ito (color-blind-safe). Course identity is also carried by the code text in every block.
const PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#B8A800", "#7A7A7A"];
const PX_PER_HOUR = 58;
const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));
const LABEL = { lecture: "Lecture", lab: "Lab", discussion: "Discussion" } as const;

export default function ScheduleGrid({ schedule, from, to }: { schedule: Schedule; from: number; to: number }) {
  const codes = schedule.courses.map((c) => c.code);
  const color = (code: string) => PALETTE[codes.indexOf(code) % PALETTE.length];
  const timed = schedule.sections.filter((s): s is Section & { start: string; end: string } => s.days.length > 0 && !!s.start && !!s.end);
  const untimed = schedule.sections.filter((s) => !(s.days.length > 0 && s.start && s.end));
  const hours = Array.from({ length: to - from }, (_, i) => from + i);

  return (
    <div>
      <div role="group" aria-label={`Weekly grid for schedule ${schedule.rank}`} className="overflow-x-auto">
        <div className="grid min-w-[560px] grid-cols-[3rem_repeat(5,1fr)] text-xs">
          <div />
          {DAYS.map((d) => (
            <div key={d} className="border-b border-line py-1 text-center font-medium">{d}</div>
          ))}
          <div className="relative" style={{ height: hours.length * PX_PER_HOUR }}>
            {hours.map((h, i) => (
              <span key={h} className="absolute right-1 -translate-y-1/2 opacity-70" style={{ top: i * PX_PER_HOUR }}>{String(h).padStart(2, "0")}:00</span>
            ))}
          </div>
          {DAYS.map((d) => (
            <div key={d} className="relative border-l border-line" style={{ height: hours.length * PX_PER_HOUR }}>
              {hours.map((h, i) => (
                <div key={h} className="absolute inset-x-0 border-t border-line/50" style={{ top: i * PX_PER_HOUR }} />
              ))}
              <div className="absolute inset-x-0 bg-accent/10" style={{ top: ((11 - from) * PX_PER_HOUR), height: 3 * PX_PER_HOUR }} aria-hidden="true" />
              {timed.filter((s) => s.days.includes(d)).map((s) => (
                <div
                  key={s.id}
                  className="absolute inset-x-0.5 overflow-hidden rounded-sm border-l-4 px-1 leading-tight"
                  style={{
                    top: ((mins(s.start) - from * 60) / 60) * PX_PER_HOUR,
                    height: Math.max(((mins(s.end) - mins(s.start)) / 60) * PX_PER_HOUR - 1, 18),
                    borderLeftColor: color(s.course_code),
                    background: `${color(s.course_code)}33`,
                  }}
                >
                  <div className="font-semibold">{s.course_code}</div>
                  <div>{LABEL[s.component]} {s.section_label}</div>
                  <div className="opacity-80">{s.start}–{s.end} · {s.building_code}</div>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
      <p className="mt-1 text-xs opacity-70"><span aria-hidden="true">▒</span> Shaded band = 11:00–14:00 lunch window.</p>
      {untimed.length > 0 && (
        <p className="mt-1 text-xs">
          <span aria-hidden="true">☁</span> TBA / online (no fixed time): {untimed.map((s) => `${s.course_code} ${s.section_label}`).join(", ")}
        </p>
      )}
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer">Class list (text)</summary>
        <ul className="mt-1 list-disc pl-5">
          {schedule.sections.map((s) => (
            <li key={s.id}>
              {s.course_code} {LABEL[s.component]} {s.section_label}:{" "}
              {s.days.length ? `${s.days.join("/")} ${s.start}–${s.end}, ${s.building_code ?? "?"} ${s.room ?? ""}` : "TBA / online"}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
