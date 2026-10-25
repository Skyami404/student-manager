"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { apiGet, type DiningHalls, type DiningMenu } from "@/lib/api";

const field = "mt-1 rounded border border-line bg-surface p-2";
const ICON: Record<string, string> = { vegetarian: "🥕", vegan: "🌱", gluten_free: "🌾", halal: "☪" };
const LABEL: Record<string, string> = { vegetarian: "Vegetarian", vegan: "Vegan", gluten_free: "Gluten-free", halal: "Halal" };
const HALL_KEY = "compass.menuHall";

function savedHall(): string {
  try {
    return localStorage.getItem(HALL_KEY) ?? "";
  } catch {
    return "";
  }
}

export default function MenusPage() {
  const [halls, setHalls] = useState<DiningHalls | null>(null);
  const [hallsFailed, setHallsFailed] = useState(false);
  const [hall, setHall] = useState("");
  const [menu, setMenu] = useState<{ hall: string; data: DiningMenu | null; failed: boolean }>({ hall: "", data: null, failed: false });
  const [meal, setMeal] = useState("");

  useEffect(() => {
    let live = true;
    apiGet<DiningHalls>("/dining/halls")
      .then((d) => {
        if (!live) return;
        setHalls(d);
        const saved = savedHall();
        setHall(d.halls.some((h) => h.id === saved) ? saved : d.halls[0]?.id ?? "");
      })
      .catch(() => live && setHallsFailed(true));
    return () => void (live = false);
  }, []);

  useEffect(() => {
    if (!hall) return;
    let live = true;
    try {
      localStorage.setItem(HALL_KEY, hall);
    } catch {}
    apiGet<DiningMenu>(`/dining/menu/${encodeURIComponent(hall)}`)
      .then((data) => {
        if (!live) return;
        setMenu({ hall, data, failed: false });
        setMeal((m) => (data.meals?.some((x) => x.name === m) ? m : data.meals?.[0]?.name ?? ""));
      })
      .catch(() => live && setMenu({ hall, data: null, failed: true }));
    return () => void (live = false);
  }, [hall]);

  const m = menu.hall === hall ? menu.data : null;
  const info = halls?.halls.find((h) => h.id === hall);
  const current = m?.meals?.find((x) => x.name === meal);
  const hours = (name: string) => m?.schedules?.find((s) => s.meal === name);

  return (
    <section aria-labelledby="h" className="space-y-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 id="h" className="text-xl font-semibold">Dining hall menus</h1>
        <Link href="/eat" className="text-sm text-accent underline">Plan meals around my classes →</Link>
      </div>
      <p role="note" className="rounded border border-warn p-2 text-sm"><span aria-hidden="true">⚠</span> Dietary info may be outdated; confirm with dining staff.</p>

      {hallsFailed && <p role="alert" className="text-sm text-warn"><span aria-hidden="true">✕</span> Could not load dining halls. Is the backend running?</p>}
      {!halls && !hallsFailed && <p className="text-sm opacity-70">Loading…</p>}
      {halls && halls.halls.length === 0 && (
        <p role="alert" className="text-sm text-warn"><span aria-hidden="true">✕</span> No dining halls found. Check BU_BASE and BU_API_KEY in backend/.env, then restart the backend.</p>
      )}

      {halls && halls.halls.length > 0 && (
        <label className="block max-w-sm text-sm">Dining hall
          <select value={hall} onChange={(e) => setHall(e.target.value)} className={`${field} w-full`}>
            {halls.halls.map((h) => <option key={h.id} value={h.id}>{h.name ?? h.short_name ?? h.id}</option>)}
          </select>
        </label>
      )}

      {info && (
        <p className="text-xs opacity-70">{[info.campus, info.address].filter(Boolean).join(" · ")}</p>
      )}

      {hall && menu.hall === hall && menu.failed && (
        <p role="alert" className="text-sm text-warn"><span aria-hidden="true">✕</span> Could not load this menu. The BU API key may have expired (they last one day). Put a new one in backend/.env and restart the backend.</p>
      )}
      {hall && !m && !(menu.hall === hall && menu.failed) && halls && <p className="text-sm opacity-70">Loading menu…</p>}

      {m && (
        <>
          <div className="text-sm">
            {m.open_now != null && <span><span aria-hidden="true">{m.open_now ? "●" : "○"}</span> {m.open_now ? "Open now" : "Closed now"}</span>}
            {m.status && <span>{m.open_now != null ? " · " : ""}{m.status}</span>}
            {m.date && <span className="opacity-70"> · Menu for {m.date}</span>}
          </div>
          {m.data_status !== "live" && (
            <p className="text-sm text-warn"><span aria-hidden="true">⚠</span> Showing a saved copy ({m.data_status}), not live data. The API key may be missing or expired.</p>
          )}

          {(m.meals ?? []).length === 0 ? (
            <p className="text-sm"><span aria-hidden="true">ℹ</span> No menu published for this hall today.</p>
          ) : (
            <div role="group" aria-label="Meal" className="flex flex-wrap gap-1">
              {(m.meals ?? []).map((x) => {
                const h = hours(x.name);
                return (
                  <button key={x.name} type="button" aria-pressed={meal === x.name} onClick={() => setMeal(x.name)}
                    className={`rounded border px-3 py-1 text-sm ${meal === x.name ? "border-accent bg-accent font-semibold text-white dark:text-black" : "border-line bg-surface"}`}>
                    {meal === x.name && <span aria-hidden="true">✓ </span>}{x.name}{h ? ` · ${h.opens_at}–${h.closes_at}` : ""}
                  </button>
                );
              })}
            </div>
          )}

          {current && (
            <div className="grid gap-3 md:grid-cols-2">
              {current.stations.map((st, i) => (
                <div key={(st.name ?? "") + i} className="rounded border border-line p-3 text-sm">
                  <h2 className="mb-1 font-medium">{st.name ?? `Station ${i + 1}`}</h2>
                  <ul className="space-y-1">
                    {st.items.map((it) => {
                      const tags = Object.keys(ICON).filter((k) => it[k as keyof typeof it]);
                      return (
                        <li key={it.id}>
                          {it.name}
                          {tags.map((k) => <span key={k} title={LABEL[k]} className="ml-1"><span aria-hidden="true">{ICON[k]}</span><span className="sr-only"> {LABEL[k]}</span></span>)}
                        </li>
                      );
                    })}
                    {st.items.length === 0 && <li className="opacity-70">Nothing listed.</li>}
                  </ul>
                </div>
              ))}
            </div>
          )}
          <p className="text-xs opacity-70">
            {Object.keys(ICON).map((k) => `${ICON[k]} ${LABEL[k]}`).join("  ")}. Menus and ingredients can change. If you have a food allergy, speak with BU Dining staff before ordering.
          </p>
        </>
      )}
    </section>
  );
}
