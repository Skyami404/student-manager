"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import AlertsCard from "@/components/AlertsCard";
import LeaveByCard from "@/components/LeaveByCard";
import { RISK } from "@/components/ScheduleGrid";
import { apiGet, type Meals } from "@/lib/api";
import { classesOn, mins, todayName, useNow } from "@/lib/schedule";
import { useSelected } from "@/lib/selected";

const card = "rounded border border-line p-4";

function MealsToday({ sid, day }: { sid: string; day: string }) {
  const [res, setRes] = useState<{ sid: string; data: Meals | null; failed: boolean } | null>(null);
  useEffect(() => {
    let live = true;
    apiGet<Meals>(`/meals?day=${day}&schedule_id=${sid}`)
      .then((data) => live && setRes({ sid, data, failed: false }))
      .catch(() => live && setRes({ sid, data: null, failed: true }));
    return () => void (live = false);
  }, [sid, day]);
  const d = res?.sid === sid ? res.data : null;
  return (
    <section aria-labelledby="mw" className={card}>
      <h2 id="mw" className="text-lg font-semibold">Meal windows today</h2>
      {res?.failed && <p className="mt-1 text-sm text-warn"><span aria-hidden="true">✕</span> Dining data unavailable.</p>}
      {!d && !res?.failed && <p className="mt-1 text-sm opacity-70">Loading…</p>}
      {d && d.gaps.length === 0 && <p className="mt-1 text-sm">No gaps of {d.meal_minutes}+ minutes in today&apos;s classes.</p>}
      <ul className="mt-1 space-y-2 text-sm">
        {d?.gaps.map((g) => {
          const o = g.options[0];
          return (
            <li key={g.kind + g.start}>
              <span aria-hidden="true">{g.fits === null ? "?" : g.fits ? "✓" : "✕"}</span> <span className="font-medium">{g.start}–{g.end}</span>{" "}
              {g.location_unknown ? "· location unknown, can't tell if a meal fits" : o ? <>· {o.hall} {o.meal.toLowerCase()}, start {o.start_between[0]}–{o.start_between[1]} (walk {o.walk_to_min}{o.walk_from_min ? `+${o.walk_from_min}` : ""} min)</> : "· no open hall fits"}
            </li>
          );
        })}
      </ul>
      {d?.notes.map((n) => <p key={n} className="mt-1 text-xs text-warn"><span aria-hidden="true">⚠</span> {n}</p>)}
      <p className="mt-2 text-xs opacity-70">Dietary info may be outdated; confirm with dining staff. Filters are in the Eat tab.</p>
    </section>
  );
}

export default function BriefingPage() {
  const sel = useSelected();
  const now = useNow();
  if (!now) {
    return (
      <section aria-labelledby="h" className="mx-auto max-w-xl">
        <h1 id="h" className="text-xl font-semibold">Briefing</h1>
        <p className="mt-2 text-sm opacity-70">Loading…</p>
      </section>
    );
  }
  const day = todayName(now);
  const label = now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });

  if (!sel) {
    return (
      <section aria-labelledby="h" className="mx-auto max-w-xl">
        <h1 id="h" className="text-xl font-semibold">Briefing · {label}</h1>
        <p className="mt-2 text-sm">No schedule selected yet. Generate one in <Link href="/build" className="text-accent underline">Build</Link> and choose “Use this schedule”.</p>
      </section>
    );
  }
  const s = sel.schedule;
  const today = classesOn(s.sections, day);
  const nowMin = now.getHours() * 60 + now.getMinutes();
  const trs = s.metrics.transitions.filter((t) => t.day === day);
  const count = (k: "green" | "amber" | "red" | "unknown") => trs.filter((t) => t.risk === k).length;
  const assessed = trs.length - count("unknown");
  const level = count("red") ? "red" : count("amber") ? "amber" : assessed > 0 ? "green" : "unknown";
  const verdict = { green: "Low", amber: "Medium", red: "High", unknown: "Not assessed" }[level];

  return (
    <section aria-labelledby="h" className="mx-auto max-w-xl space-y-4">
      <h1 id="h" className="text-xl font-semibold">Briefing <span className="block text-sm font-normal opacity-70 sm:inline">· {label} · sample (synthetic) catalog</span></h1>

      <LeaveByCard schedule={s} todayOnly title="Leave-by: next class today" />

      <section aria-labelledby="tc" className={card}>
        <h2 id="tc" className="text-lg font-semibold">Today&apos;s classes</h2>
        {today.length === 0 && <p className="mt-1 text-sm"><span aria-hidden="true">☕</span> No classes today ({day}).</p>}
        <ul className="mt-1 space-y-2">
          {today.map((c) => {
            const state = mins(c.end!) <= nowMin ? "done" : mins(c.start!) <= nowMin ? "now" : "next";
            return (
              <li key={c.id} className="flex items-baseline justify-between gap-2 text-sm">
                <span><span className="font-medium">{c.start}–{c.end}</span> · {c.course_code} <span className="opacity-70">{c.component} {c.section_label}</span></span>
                <span className="whitespace-nowrap text-xs">
                  {c.location_status === "unknown" ? <><span aria-hidden="true">? </span>location unknown</> : <>{c.building_code} {c.room}</>} <span aria-hidden="true">{state === "done" ? "✓" : state === "now" ? "●" : "○"}</span>
                  <span className="sr-only">{state === "done" ? "finished" : state === "now" ? "in progress" : "upcoming"}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <AlertsCard />
      <MealsToday sid={s.id} day={day} />

      <section aria-labelledby="tr" className={card}>
        <h2 id="tr" className="text-lg font-semibold">Transit risk today</h2>
        <p className="mt-1 text-sm font-medium">
          <span className="rounded px-2 py-0.5 font-bold" style={{ background: RISK[level].bg, color: RISK[level].fg }}>
            <span aria-hidden="true">{RISK[level].icon}</span> {verdict}{level === "unknown" ? "" : " risk"}
          </span>{" "}
          {trs.length === 0 ? "· no back-to-back walks today" : `· ${trs.length} walk(s): ${count("green")} OK, ${count("amber")} tight, ${count("red")} risky${count("unknown") ? `, ${count("unknown")} not assessed (location unknown)` : ""}`}
        </p>
        <ul className="mt-2 space-y-1 text-sm">
          {trs.filter((t) => t.risk !== "green").map((t, i) => (
            <li key={i}><span aria-hidden="true">{RISK[t.risk].icon}</span> {t.risk_why}</li>
          ))}
        </ul>
        <p className="mt-2 text-xs opacity-70">Walking time only (assumed ±20% spread). Shuttle delay risk for your first class is in the Leave-by card; delay estimates use synthetic placeholder data until enough real predictions are logged.</p>
      </section>
    </section>
  );
}
