"use client";
import { useEffect, useState } from "react";
import { saveLocal, useLocal } from "@/lib/local";

type Mode = "focus" | "short" | "long";
type Timer = { mode: Mode; endAt: number | null; left: number; rounds: number; focusMin: number; ringing?: boolean };
const KEY = "compass.pomodoro.v1";
const START: Timer = { mode: "focus", endAt: null, left: 25 * 60, rounds: 0, focusMin: 25 };
const NAME: Record<Mode, string> = { focus: "Focus", short: "Short break", long: "Long break" };
const lengthOf = (m: Mode, t: Timer) => (m === "focus" ? t.focusMin : m === "short" ? 5 : 15) * 60;

function ding() {
  // Plays once; falls back to a synthesized beep if the file cannot play.
  new Audio("/pomodoro/ding.mp3").play().catch(beep);
}

function beep() {
  try {
    const ctx = new AudioContext();
    [0, 0.35, 0.7].forEach((at) => {
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = 880;
      g.gain.setValueAtTime(0.2, ctx.currentTime + at);
      g.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + at + 0.3);
      o.connect(g).connect(ctx.destination);
      o.start(ctx.currentTime + at);
      o.stop(ctx.currentTime + at + 0.3);
    });
  } catch {
    /* no audio available */
  }
}

export default function PomodoroCard() {
  const t = useLocal<Timer>(KEY, START);
  const [now, setNow] = useState(() => Date.now());
  const left = t.endAt ? Math.max(0, Math.round((t.endAt - now) / 1000)) : t.left;
  const running = t.endAt !== null;

  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(id);
  }, [running]);

  // Time is up: ring, then move to the next phase (paused, so the student chooses when to start).
  useEffect(() => {
    if (!running || left > 0) return;
    ding();
    const rounds = t.mode === "focus" ? t.rounds + 1 : t.rounds;
    const next: Mode = t.mode !== "focus" ? "focus" : rounds % 4 === 0 ? "long" : "short";
    if (typeof Notification !== "undefined" && Notification.permission === "granted") new Notification(`${NAME[t.mode]} done`, { body: `Next: ${NAME[next]}` });
    saveLocal<Timer>(KEY, { ...t, mode: next, endAt: null, rounds, left: lengthOf(next, t), ringing: true });
  }, [running, left, t]);

  useEffect(() => {
    if (!running) return;
    const old = document.title;
    document.title = `${String(Math.floor(left / 60)).padStart(2, "0")}:${String(left % 60).padStart(2, "0")} · ${NAME[t.mode]}`;
    return () => void (document.title = old);
  }, [running, left, t.mode]);

  const start = () => {
    if (typeof Notification !== "undefined" && Notification.permission === "default") Notification.requestPermission().catch(() => {});
    const at = Date.now();
    setNow(at);
    saveLocal<Timer>(KEY, { ...t, endAt: at + left * 1000, ringing: false });
  };
  const pause = () => saveLocal<Timer>(KEY, { ...t, endAt: null, left });
  const pick = (mode: Mode, focusMin = t.focusMin) => saveLocal<Timer>(KEY, { ...t, mode, focusMin, endAt: null, ringing: false, left: lengthOf(mode, { ...t, focusMin }) });

  const total = lengthOf(t.mode, t);
  const pct = total ? (1 - left / total) * 100 : 0;
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  const btn = "rounded border border-line px-3 py-1.5 text-sm";

  return (
    <section aria-labelledby="pm" className="rounded border border-line p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="pm" className="text-lg font-semibold">Pomodoro timer</h2>
        <span className="text-xs opacity-70">{t.rounds} focus round{t.rounds === 1 ? "" : "s"} done</span>
      </div>
      <div role="group" aria-label="Timer mode" className="mt-2 flex flex-wrap gap-1">
        {(["focus", "short", "long"] as Mode[]).map((m) => (
          <button key={m} type="button" aria-pressed={t.mode === m} onClick={() => pick(m)}
            className={`rounded px-2 py-0.5 text-xs ${t.mode === m ? "bg-accent font-medium text-white dark:text-black" : "border border-line"}`}>
            {NAME[m]}
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-center gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={t.ringing ? "/pomodoro/splat.png" : "/pomodoro/tomato.png"} alt={t.ringing ? "Time is up" : ""} width={72} height={72}
          className={`h-18 w-18 ${t.ringing ? "" : running ? "animate-pulse" : ""}`} style={{ imageRendering: "pixelated" }} />
        <p className="font-mono text-5xl font-semibold tabular-nums" aria-live="off">{mm}:{ss}</p>
      </div>
      {t.ringing && <p role="status" className="mt-1 text-center text-sm font-medium text-warn">Time is up! Press Reset or Start when you are ready.</p>}
      <div className="mt-2 h-2 overflow-hidden rounded bg-surface" role="progressbar" aria-label={`${NAME[t.mode]} progress`} aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full bg-accent transition-[width]" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-3 flex flex-wrap items-center justify-center gap-2">
        {running
          ? <button type="button" onClick={pause} className={btn}>Pause</button>
          : <button type="button" onClick={start} className="rounded bg-accent px-4 py-1.5 text-sm font-medium text-white dark:text-black">{left < total ? "Resume" : "Start"}</button>}
        <button type="button" onClick={() => pick(t.mode)} className={btn}>Reset</button>
        <label className="text-xs">Focus length{" "}
          <select value={t.focusMin} onChange={(e) => pick(t.mode, Number(e.target.value))} className="rounded border border-line bg-surface p-1">
            {[15, 25, 45, 50].map((n) => <option key={n} value={n}>{n} min</option>)}
          </select>
        </label>
      </div>
      <p className="mt-2 text-xs opacity-70">Focus, then a 5 minute break. Every 4th break is 15 minutes. It rings when time is up, and keeps going if you switch pages.</p>
    </section>
  );
}
