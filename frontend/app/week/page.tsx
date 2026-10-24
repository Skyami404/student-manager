"use client";
import Link from "next/link";
import AlertsCard from "@/components/AlertsCard";
import CatalogTag from "@/components/CatalogTag";
import FriendsPanel from "@/components/FriendsPanel";
import IcsButton from "@/components/IcsButton";
import LeaveByCard from "@/components/LeaveByCard";
import ScheduleGrid, { RISK } from "@/components/ScheduleGrid";
import { useSelected } from "@/lib/selected";

const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));

export default function WeekPage() {
  const sel = useSelected();
  if (!sel) {
    return (
      <section aria-labelledby="h">
        <h1 id="h" className="text-xl font-semibold">Week</h1>
        <p className="mt-2 text-sm">No schedule selected yet. Generate schedules in <Link href="/build" className="text-accent underline">Build</Link> and choose “Use this schedule”.</p>
      </section>
    );
  }
  const s = sel.schedule;
  const times = s.sections.filter((x) => x.start && x.end);
  const from = Math.min(8, ...times.map((x) => Math.floor(mins(x.start!) / 60)));
  const to = Math.max(18, ...times.map((x) => Math.ceil(mins(x.end!) / 60)));
  const tr = s.metrics.transitions;

  return (
    <section aria-labelledby="h" className="space-y-6">
      <h1 id="h" className="text-xl font-semibold">Week <span className="text-sm font-normal opacity-70">· {s.courses.map((c) => c.code).join(", ")} · <CatalogTag /></span></h1>
      <IcsButton scheduleId={s.id} />
      <div className="grid gap-4 md:grid-cols-2">
        <LeaveByCard schedule={s} />
        <AlertsCard />
      </div>

      <div>
        <h2 className="mb-2 text-lg font-semibold">Weekly grid with transition risk</h2>
        <ScheduleGrid schedule={s} from={from} to={to} showRisk />
        <ul className="mt-2 flex flex-wrap gap-3 text-xs" aria-label="Risk legend">
          {(Object.keys(RISK) as (keyof typeof RISK)[]).map((k) => (
            <li key={k} className="rounded px-2 py-0.5 font-bold" style={{ background: RISK[k].bg, color: RISK[k].fg }}>
              <span aria-hidden="true">{RISK[k].icon}</span> {RISK[k].word}: {k === "green" ? "≥85% on time" : k === "amber" ? "50–85%" : k === "red" ? "<50%" : "location unknown, not assessed"}
            </li>
          ))}
        </ul>
        <p className="mt-1 text-xs opacity-70">Risk badge sits on the class you are walking to. It reflects walking time only (an assumed ±20% spread); the dorm-to-first-class leg is in the Leave-by card. ≈ marks an approximate walking time (a building is missing from the buildings table or its location is unverified). Classes with no building, “No Room”, or on the medical campus have no walking time, so they show “Unknown” and are left out of the risk checks.</p>
      </div>

      {tr.some((t) => t.risk !== "green") && (
        <div>
          <h2 className="mb-1 text-lg font-semibold">Why these transitions are flagged</h2>
          <ul className="space-y-1 text-sm">
            {tr.filter((t) => t.risk !== "green").map((t, i) => (
              <li key={i}><span aria-hidden="true">{RISK[t.risk].icon}</span> <span className="font-medium">{t.day}</span>: {t.risk_why}</li>
            ))}
          </ul>
        </div>
      )}

      <FriendsPanel schedule={s} />
    </section>
  );
}
