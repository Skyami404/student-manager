"use client";
import { useEffect, useState, useSyncExternalStore } from "react";
import { apiGet, type LeaveBy } from "@/lib/api";
import { nextClass } from "@/lib/schedule";
import { useSelected } from "@/lib/selected";

const KEY = "compass.pet.hidden";
const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => (listeners.add(cb), () => void listeners.delete(cb));
function useHidden() {
  return useSyncExternalStore(subscribe, () => localStorage.getItem(KEY) === "1", () => true);
}
function setHidden(v: boolean) {
  localStorage.setItem(KEY, v ? "1" : "0");
  listeners.forEach((l) => l());
}

type PetState = "idle" | "walking" | "sleeping";
const LABEL: Record<PetState, string> = { idle: "Idle", walking: "Walking: time to head out", sleeping: "Sleeping: no classes to go to" };

/** sleeping: no classes left today. walking: leave-by is 15 min away or less (or overdue). idle: otherwise. */
function usePetState(): { state: PetState; note: string } {
  const sel = useSelected();
  const [s, setS] = useState<{ state: PetState; note: string }>({ state: "sleeping", note: "" });

  useEffect(() => {
    let live = true;
    const run = async () => {
      const sections = sel?.schedule.sections ?? [];
      const next = nextClass(sections, new Date(), true);
      if (!sel || !next) {
        if (live) setS({ state: "sleeping", note: sel ? "No more classes today" : "No schedule selected" });
        return;
      }
      try {
        const lb = await apiGet<LeaveBy>(`/leave-by?schedule_id=${sel.schedule.id}&class_id=${encodeURIComponent(next.id)}&day=${next.day}`);
        const m = Math.round((new Date(lb.leave_at_iso).getTime() - Date.now()) / 60000);
        if (!live) return;
        setS(m <= 15 ? { state: "walking", note: m <= 0 ? "Leave now" : `Leave in ${m} min` } : { state: "idle", note: `Leave by ${lb.leave_at}` });
      } catch {
        if (live) setS({ state: "idle", note: "" });
      }
    };
    run();
    const id = setInterval(run, 60_000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, [sel]);

  return s;
}

export function PetToggle() {
  const hidden = useHidden();
  return (
    <button type="button" aria-pressed={!hidden} onClick={() => setHidden(!hidden)} className="rounded border border-line bg-surface px-3 py-1.5 text-sm">
      <span aria-hidden="true">🐾</span> Pet: {hidden ? "off" : "on"}
    </button>
  );
}

export default function PetWidget() {
  const hidden = useHidden();
  const { state, note } = usePetState();
  if (hidden) return null;
  return (
    <aside aria-label="Pet" className="fixed bottom-3 right-3 z-20 flex flex-col items-center" data-testid="pet" data-state={state}>
      {note && (
        <span className="mb-1 rounded-full border border-line bg-background px-2 py-0.5 text-xs shadow" aria-live="polite">
          {state === "sleeping" ? "💤 " : state === "walking" ? "🚶 " : ""}{note}
        </span>
      )}
      <div className="pet-sprite" data-state={state} role="img" aria-label={`Boston Terrier pet. ${LABEL[state]}`} />
      <button type="button" onClick={() => setHidden(true)} className="mt-0.5 rounded border border-line bg-surface px-1.5 text-xs" aria-label="Hide pet">
        <span aria-hidden="true">✕</span> Hide
      </button>
    </aside>
  );
}
