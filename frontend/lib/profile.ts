import { useMemo, useSyncExternalStore } from "react";

export type Profile = { dormCode: string; requiredCourses: string[]; targetCredits: number; completedHub?: string[] };

const KEY = "compass.profile.v1";
const listeners = new Set<() => void>();

function subscribe(cb: () => void) {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => e.key === KEY && cb();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

export function saveProfile(p: Profile) {
  localStorage.setItem(KEY, JSON.stringify(p));
  listeners.forEach((l) => l());
}

/** ready=false during SSR/hydration; profile=null when onboarding has not been completed. */
export function useProfile(): { profile: Profile | null; ready: boolean } {
  const raw = useSyncExternalStore<string | null | undefined>(
    subscribe,
    () => localStorage.getItem(KEY),
    () => undefined,
  );
  const profile = useMemo(() => {
    if (!raw) return null;
    try {
      return JSON.parse(raw) as Profile;
    } catch {
      return null;
    }
  }, [raw]);
  return { profile, ready: raw !== undefined };
}
