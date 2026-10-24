"use client";
import { useSyncExternalStore } from "react";

const subscribe = (cb: () => void) => {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => mo.disconnect();
};

export default function ThemeToggle() {
  const dark = useSyncExternalStore(subscribe, () => document.documentElement.classList.contains("dark"), () => false);
  function toggle() {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("compass.theme", next ? "dark" : "light");
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={dark}
      className="rounded border border-line bg-surface px-3 py-1.5 text-sm"
    >
      <span aria-hidden="true">{dark ? "☾" : "☀"}</span> {dark ? "Dark" : "Light"} mode
    </button>
  );
}
