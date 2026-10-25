import { useMemo, useSyncExternalStore } from "react";

// Small JSON values kept in this browser's localStorage, shared live between components.
const listeners = new Set<() => void>();
const subscribe = (cb: () => void) => {
  listeners.add(cb);
  window.addEventListener("storage", cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", cb);
  };
};

const read = (key: string) => {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
};

export function saveLocal<T>(key: string, value: T) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* private mode / storage full: keep going without saving */
  }
  listeners.forEach((l) => l());
}

export function useLocal<T>(key: string, fallback: T): T {
  const raw = useSyncExternalStore<string | null>(subscribe, () => read(key), () => null);
  return useMemo(() => {
    try {
      return raw ? (JSON.parse(raw) as T) : fallback;
    } catch {
      return fallback;
    }
    // fallback is a constant at every call site
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [raw]);
}

export type Todo = { id: string; text: string; done: boolean; due?: string | null };
export const TODOS = "compass.todos.v1";

export function addTodo(list: Todo[], text: string, due?: string | null, id?: string) {
  if (!text.trim() || (id && list.some((t) => t.id === id))) return;
  saveLocal<Todo[]>(TODOS, [...list, { id: id ?? `t${Date.now()}`, text: text.trim(), done: false, due: due ?? null }]);
}
