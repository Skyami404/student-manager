"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, type Meals } from "@/lib/api";
import { useNow, todayName } from "@/lib/schedule";
import { useSelected } from "@/lib/selected";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const ICON: Record<string, string> = { vegetarian: "🥕", vegan: "🌱", gluten_free: "🌾", halal: "☪" };

export default function EatPage() {
  const sel = useSelected();
  const sid = sel?.schedule.id;
  const now = useNow();
  const [picked, setPicked] = useState<string | null>(null);
  const day = picked ?? (now ? todayName(now) : null); // null until the browser clock is available
  const [diet, setDiet] = useState<string[]>([]);
  const key = `${sid}|${day}|${diet.join(",")}`;
  const [res, setRes] = useState<{ key: string; data: Meals | null; failed: boolean }>({ key: "", data: null, failed: false });
  const [filters, setFilters] = useState<Meals["diet_filters_available"]>([]);

  useEffect(() => {
    if (!day) return;
    let live = true;
    const q = new URLSearchParams({ day, diet: diet.join(",") });
    if (sid) q.set("schedule_id", sid);
    apiGet<Meals>(`/meals?${q}`)
      .then((data) => live && (setRes({ key, data, failed: false }), setFilters(data.diet_filters_available)))
      .catch(() => live && setRes({ key, data: null, failed: true }));
    return () => void (live = false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const d = res.key === key ? res.data : null;
  const toggle = (id: string) => setDiet((x) => (x.includes(id) ? x.filter((i) => i !== id) : [...x, id]));

  return (
    <section aria-labelledby="h" className="space-y-5">
      <h1 id="h" className="text-xl font-semibold">Eat</h1>
      <p role="note" className="rounded border border-warn p-2 text-sm"><span aria-hidden="true">⚠</span> Dietary info may be outdated; confirm with dining staff.</p>

      <div role="group" aria-label="Day" className="flex flex-wrap gap-1">
        {DAYS.map((x) => (
          <button key={x} type="button" aria-pressed={day === x} onClick={() => setPicked(x)}
            className={`rounded border px-3 py-1 text-sm ${day === x ? "border-accent bg-accent font-semibold text-white dark:text-black" : "border-line bg-surface"}`}>
            {day === x && <span aria-hidden="true">✓ </span>}{x}
          </button>
        ))}
      </div>

      {filters.length > 0 && (
        <div role="group" aria-label="Dietary filters" className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium">Dietary:</span>
          {filters.map((f) => (
            <button key={f.id} type="button" aria-pressed={diet.includes(f.id)} onClick={() => toggle(f.id)}
              className={`rounded-full border px-3 py-1 text-sm ${diet.includes(f.id) ? "border-accent bg-accent font-semibold text-white dark:text-black" : "border-line bg-surface"}`}>
              <span aria-hidden="true">{diet.includes(f.id) ? "✓" : ICON[f.id]}</span> {f.label}
            </button>
          ))}
        </div>
      )}
      {d && <p className="text-xs opacity-70"><span aria-hidden="true">ℹ</span> {d.allergen_filter.reason}</p>}

      {res.failed && <p role="alert" className="text-sm text-warn"><span aria-hidden="true">✕</span> Could not load dining data. Is the backend running?</p>}
      {!d && !res.failed && <p className="text-sm opacity-70">Loading…</p>}
      {d && (
        <>
          {d.notes.map((n) => <p key={n} className="text-sm text-warn"><span aria-hidden="true">⚠</span> {n}</p>)}

          <div>
            <h2 className="mb-2 text-lg font-semibold">Dining halls · {d.day}{d.hours_source === "today" ? " (today)" : d.hours_source === "last_observed" ? ` (hours seen ${d.hours_date})` : ""}</h2>
            <ul className="grid gap-2 md:grid-cols-3">
              {d.halls.map((h) => (
                <li key={h.id} className="rounded border border-line p-3 text-sm">
                  <div className="font-medium">{h.short_name}</div>
                  <div className="text-xs opacity-70">{h.campus} · {h.address}</div>
                  {h.open_now !== null && <div className="mt-1"><span aria-hidden="true">{h.open_now ? "●" : "○"}</span> {h.open_now ? "Open now" : "Closed now"}{h.status_text ? ` · ${h.status_text}` : ""}</div>}
                  <ul className="mt-1 text-xs">
                    {h.meals.map((m) => (
                      <li key={m.meal}>{m.meal} {m.opens_at}–{m.closes_at}{d.diet.length > 0 && m.matching_items !== null ? ` · ${m.matching_items} of ${m.total_items} items match` : ""}</li>
                    ))}
                    {h.meals.length === 0 && <li>Hours not available for {d.day}.</li>}
                  </ul>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h2 className="mb-2 text-lg font-semibold">Meal windows in your {d.day} schedule</h2>
            {!sid && <p className="text-sm">No schedule selected. Choose one in <Link href="/build" className="text-accent underline">Build</Link> to find gaps.</p>}
            {sid && d.gaps.length === 0 && <p className="text-sm"><span aria-hidden="true">ℹ</span> No classes on {d.day}, or no gap of {d.meal_minutes}+ minutes.</p>}
            <ul className="space-y-3">
              {d.gaps.map((g) => (
                <li key={g.kind + g.start} className="rounded border border-line p-3 text-sm">
                  <div className="font-medium">
                    <span aria-hidden="true">{g.fits === null ? "?" : g.fits ? "✓" : "✕"}</span> {g.start}–{g.end} ({g.kind.replace("_", " ")}) · {g.fits === null ? "location unknown, can't tell if a meal fits" : g.fits ? "a meal fits" : "no meal fits"}
                  </div>
                  <p className="text-xs opacity-80">{g.why}</p>
                  <ul className="mt-2 space-y-1">
                    {g.options.slice(0, 4).map((o) => (
                      <li key={o.hall_id + o.meal} className="rounded bg-surface p-2">
                        <span className="font-medium">{o.hall}</span> · {o.meal} · start between {o.start_between[0]} and {o.start_between[1]} · walk {o.walk_to_min}{o.walk_from_min ? ` + ${o.walk_from_min}` : ""} min
                        {d.diet.length > 0 && o.matching_items !== null && (
                          <div className="text-xs"><span aria-hidden="true">{o.matching_items > 0 ? "✓" : "✕"}</span> {o.matching_items} of {o.total_items} items match{o.examples.length ? `: ${o.examples.join(", ")}` : ""}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </div>
          <p className="text-xs opacity-70">{d.allergy_notice} Dining coordinates are approximate (synthetic seed), so walking times are estimates.</p>
        </>
      )}
    </section>
  );
}
