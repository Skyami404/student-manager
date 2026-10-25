"use client";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

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

export function PetToggle() {
  const hidden = useHidden();
  return (
    <button type="button" aria-pressed={!hidden} onClick={() => setHidden(!hidden)} className="rounded border border-line bg-surface px-3 py-1.5 text-sm">
      <span aria-hidden="true">🐾</span> Pet: {hidden ? "off" : "on"}
    </button>
  );
}

/* Shimeji-style dog. Sprites live in /public/pet/shimeN.png (128x160, feet at bottom centre, facing left).
   Runs at 25 ticks a second like Shimeji, so frame timings match the desktop version's actions.xml. */
const SIZE = 0.75; // 1 = full 128x160 sprite
const W = 128 * SIZE;
const H = 160 * SIZE;
const TICK = 40;
const GRAVITY = 1.2;
const PET_AT = 90; // how much petting it takes before he gets happy

type Mode = "stand" | "sit" | "walk" | "run" | "sleep" | "eat" | "pet" | "drag" | "fall" | "bounce";
type Sim = {
  x: number; // left edge, px
  y: number; // height above the bottom of the window, px
  vx: number;
  vy: number;
  mode: Mode;
  t: number; // ticks spent in the current mode
  dur: number;
  targetX: number;
  facingRight: boolean;
  petting: number;
  onHead: boolean;
  grab: { dx: number; dy: number; lastX: number; lastY: number } | null;
  press?: { x: number; y: number } | null; // button held but not moved far yet: still petting, not dragging
};
type View = { x: number; y: number; frame: number; facingRight: boolean; mode: Mode };

const SPRITES = [1, 2, 3, 4, 5, 6, 10, 11, 18, 19, 26, 27, 28, 29, 30, 31, 32, 33];
const LABEL: Record<Mode, string> = {
  stand: "Standing", sit: "Sitting", walk: "Walking", run: "Running", sleep: "Sleeping", eat: "Eating",
  pet: "Happy: being petted", drag: "Being carried", fall: "Falling", bounce: "Landing",
};

function frameFor(s: Sim): number {
  const t = s.t;
  switch (s.mode) {
    case "walk": return Math.floor(t / 6) % 2 ? 3 : 2;
    case "run": return Math.floor(t / 3) % 2 ? 3 : 2;
    case "sit": return 10;
    case "pet": return 11;
    case "sleep": return [26, 27, 28, 29][Math.floor(t / 15) % 4];
    case "eat": return t < 10 ? (t < 5 ? 30 : 31) : Math.floor(t / 5) % 2 ? 33 : 32;
    case "drag": return Math.floor(t / 5) % 2 ? 6 : 5;
    case "fall": return 4;
    case "bounce": return t < 4 ? 18 : 19;
    default: return 1;
  }
}

const rand = (a: number, b: number) => a + Math.random() * (b - a);
const DURATION: Partial<Record<Mode, [number, number]>> = { stand: [100, 200], sit: [250, 500], sleep: [600, 1500], eat: [140, 280] };

function setMode(s: Sim, mode: Mode) {
  s.mode = mode;
  s.t = 0;
  const d = DURATION[mode];
  s.dur = d ? rand(d[0], d[1]) : 0;
}

function pickNext(s: Sim, still: boolean) {
  // Same weights as the desktop behaviors.xml.
  const weights: [Mode, number][] = [
    ["stand", 200], ["sit", 200], ["sleep", 150], ["eat", 150],
    ["walk", still ? 0 : 300], ["run", still ? 0 : 100],
  ];
  let r = Math.random() * weights.reduce((n, [, w]) => n + w, 0);
  setMode(s, weights.find(([, w]) => (r -= w) < 0)?.[0] ?? "stand");
  if (s.mode === "walk" || s.mode === "run") {
    s.targetX = rand(0, Math.max(0, window.innerWidth - W));
    s.facingRight = s.targetX > s.x;
  }
}

export default function PetWidget() {
  const hidden = useHidden();
  const sim = useRef<Sim | null>(null);
  const [view, setView] = useState<View | null>(null);

  useEffect(() => {
    if (hidden) return;
    SPRITES.forEach((n) => (new Image().src = `/pet/shime${n}.png`));
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const s: Sim = sim.current ?? {
      x: window.innerWidth - W - 24, y: 0, vx: 0, vy: 0, mode: "stand", t: 0, dur: 50,
      targetX: 0, facingRight: false, petting: 0, onHead: false, grab: null,
    };
    sim.current = s;

    const id = setInterval(() => {
      const maxX = Math.max(0, window.innerWidth - W);
      s.t++;
      // Petting builds up while the mouse is on his head (faster if it moves) and slowly wears off.
      s.petting = Math.max(0, s.petting + (s.onHead ? 3 : 0) - 1.5);
      if (s.onHead && s.petting > 40 && (s.mode === "walk" || s.mode === "run")) setMode(s, "stand");
      if (s.petting >= PET_AT && !["drag", "fall", "bounce", "pet"].includes(s.mode)) setMode(s, "pet");

      switch (s.mode) {
        case "drag":
          break;
        case "fall":
          s.vy -= GRAVITY;
          s.y += s.vy;
          s.x += s.vx;
          s.vx *= 0.97;
          if (s.x < 0 || s.x > maxX) s.vx = -s.vx * 0.5;
          if (s.y <= 0) {
            s.y = s.vx = s.vy = 0;
            setMode(s, "bounce");
          }
          break;
        case "bounce":
          if (s.t >= 8) setMode(s, "stand");
          break;
        case "walk":
        case "run": {
          const step = s.mode === "run" ? 4 : 2;
          const d = s.targetX - s.x;
          s.x += Math.sign(d) * Math.min(step, Math.abs(d));
          if (Math.abs(d) <= step) pickNext(s, still);
          break;
        }
        case "pet":
          // Stay happy while he's being petted, then 2 more seconds.
          if (s.onHead) s.t = 0;
          if (s.t >= 50) {
            s.petting = 0;
            pickNext(s, still);
          }
          break;
        default:
          if (s.t >= s.dur) pickNext(s, still);
      }
      s.x = Math.min(maxX, Math.max(0, s.x));
      setView({ x: s.x, y: s.y, frame: frameFor(s), facingRight: s.facingRight, mode: s.mode });
    }, TICK);
    return () => clearInterval(id);
  }, [hidden]);

  if (hidden || !view) return null;

  const onPointerDown = (e: React.PointerEvent) => {
    const s = sim.current;
    if (!s) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    s.press = { x: e.clientX, y: e.clientY };
  };
  const startDrag = (s: Sim, e: React.PointerEvent) => {
    s.press = null;
    s.grab = { dx: e.clientX - s.x, dy: window.innerHeight - e.clientY - s.y, lastX: e.clientX, lastY: e.clientY };
    s.petting = 0;
    s.onHead = false;
    setMode(s, "drag");
  };
  const onPointerMove = (e: React.PointerEvent) => {
    const s = sim.current;
    if (!s) return;
    // Holding the button and moving a long way picks him up; a click or a short rub is petting.
    if (s.press && Math.hypot(e.clientX - s.press.x, e.clientY - s.press.y) > 40) startDrag(s, e);
    if (s.grab) {
      s.vx = (e.clientX - s.grab.lastX) * 0.5;
      s.vy = (s.grab.lastY - e.clientY) * 0.5;
      s.grab.lastX = e.clientX;
      s.grab.lastY = e.clientY;
      s.x = e.clientX - s.grab.dx;
      s.y = Math.max(0, window.innerHeight - e.clientY - s.grab.dy);
      return;
    }
    // His head is roughly the top 60% of the picture (measured on screen, so zoom and size changes don't matter).
    const box = e.currentTarget.getBoundingClientRect();
    s.onHead = e.clientY - box.top < box.height * 0.6;
    if (s.onHead) s.petting += Math.min(20, Math.hypot(e.movementX, e.movementY)) * 0.15;
  };
  const onPointerUp = () => {
    const s = sim.current;
    if (s) s.press = null;
    if (!s?.grab) return;
    s.grab = null;
    setMode(s, "fall");
  };
  const onPointerLeave = () => {
    if (sim.current) sim.current.onHead = false;
  };

  return (
    <aside aria-label="Pet" className="group pointer-events-none fixed bottom-0 left-0 z-20" style={{ transform: `translate(${view.x}px, ${-view.y}px)`, width: W }} data-testid="pet" data-mode={view.mode}>
      {view.mode === "pet" && (
        <span className="absolute bottom-full left-1/2 -translate-x-1/2 animate-bounce text-xl" aria-hidden="true">💕</span>
      )}
      <div
        role="img"
        aria-label={`Boston Terrier pet. ${LABEL[view.mode]}`}
        className="pointer-events-auto touch-none select-none"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onPointerLeave={onPointerLeave}
        style={{
          width: W,
          height: H,
          cursor: view.mode === "drag" ? "grabbing" : "grab",
          backgroundImage: `url(/pet/shime${view.frame}.png)`,
          backgroundSize: "100% 100%",
          imageRendering: "pixelated",
          transform: view.facingRight ? "scaleX(-1)" : undefined,
        }}
      />
      <button type="button" onClick={() => setHidden(true)} className="pointer-events-auto absolute right-0 top-0 rounded border border-line bg-surface px-1.5 text-xs opacity-0 group-hover:opacity-100 focus:opacity-100" aria-label="Hide pet">
        <span aria-hidden="true">✕</span>
      </button>
    </aside>
  );
}
