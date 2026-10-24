import { useSyncExternalStore } from "react";

const KEY = "compass.session.v1";
const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => (listeners.add(cb), () => void listeners.delete(cb));

export function setToken(t: string | null) {
  if (t) localStorage.setItem(KEY, t);
  else localStorage.removeItem(KEY);
  listeners.forEach((l) => l());
}
/** Session token for the friends feature (null when signed out; also null during SSR). */
export function useToken(): string | null {
  return useSyncExternalStore(subscribe, () => localStorage.getItem(KEY), () => null);
}
