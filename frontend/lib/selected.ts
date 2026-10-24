import { useMemo, useSyncExternalStore } from "react";
import type { Schedule } from "./api";

export type Selected = { schedule: Schedule; dormId: string | null };
const KEY = "compass.selected.v1";
const listeners = new Set<() => void>();

const subscribe = (cb: () => void) => {
  listeners.add(cb);
  return () => void listeners.delete(cb);
};

export function saveSelected(s: Selected) {
  localStorage.setItem(KEY, JSON.stringify(s));
  listeners.forEach((l) => l());
}

export function useSelected(): Selected | null {
  const raw = useSyncExternalStore<string | null>(subscribe, () => localStorage.getItem(KEY), () => null);
  return useMemo(() => {
    try {
      return raw ? (JSON.parse(raw) as Selected) : null;
    } catch {
      return null;
    }
  }, [raw]);
}
