import { useMemo, useSyncExternalStore } from "react";
import type { Section } from "./api";

export const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
export const mins = (t: string) => Number(t.slice(0, 2)) * 60 + Number(t.slice(3));
export const todayName = (now = new Date()) => DAYS[(now.getDay() + 6) % 7];

/** Next meeting (browser local time). todayOnly limits the search to classes still to start today. */
export function nextClass(sections: Section[], now = new Date(), todayOnly = false): { id: string; day: string } | null {
  const today = (now.getDay() + 6) % 7;
  const nowMin = now.getHours() * 60 + now.getMinutes();
  let best: { id: string; day: string; at: number } | null = null;
  for (const s of sections) {
    if (!s.start || !s.days.length) continue;
    for (const d of s.days) {
      let delta = (DAYS.indexOf(d) - today + 7) % 7;
      if (delta === 0 && mins(s.start) <= nowMin) delta = 7;
      if (todayOnly && delta !== 0) continue;
      const at = delta * 1440 + mins(s.start) - nowMin;
      if (!best || at < best.at) best = { id: s.id, day: d, at };
    }
  }
  return best && { id: best.id, day: best.day };
}

export const classesOn = (sections: Section[], day: string) =>
  sections.filter((s) => s.start && s.end && s.days.includes(day)).sort((a, b) => mins(a.start!) - mins(b.start!));

const noopSubscribe = () => () => {};
/** The current time (minute precision). null on the server and while hydrating, so pages never call
 *  new Date() during prerender (Next.js Cache Components rejects that). */
export function useNow(): Date | null {
  const iso = useSyncExternalStore(
    noopSubscribe,
    () => {
      const d = new Date();
      d.setSeconds(0, 0);
      return d.toISOString();
    },
    () => null,
  );
  return useMemo(() => (iso ? new Date(iso) : null), [iso]);
}
