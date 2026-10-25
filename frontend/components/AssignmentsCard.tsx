"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";
import { TODOS, addTodo, saveLocal, useLocal, type Todo } from "@/lib/local";

export type Assignment = { id: string; title: string; course: string | null; due: string; all_day: boolean; url: string | null; source: string; manual?: boolean };
type FeedStatus = "live" | "cached" | "unavailable" | "not_set";
type AssignmentsData = { assignments: Assignment[]; feeds: Record<string, FeedStatus>; sample: boolean; days: number };

const field = "rounded border border-line bg-surface p-1.5 text-sm";
const MANUAL = "compass.assignments.manual.v1";
const DONE = "compass.assignments.done.v1";
const NONE: Assignment[] = [];
const NO_IDS: string[] = [];
const NO_TODOS: Todo[] = [];

function dueLabel(iso: string, allDay: boolean, now: Date) {
  const d = new Date(iso);
  const days = Math.round((new Date(d).setHours(0, 0, 0, 0) - new Date(now).setHours(0, 0, 0, 0)) / 86400000);
  const day = days === 0 ? "Today" : days === 1 ? "Tomorrow" : days === -1 ? "Yesterday" : d.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });
  return allDay ? day : `${day} ${d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`;
}

export default function AssignmentsCard() {
  const [res, setRes] = useState<{ data: AssignmentsData | null; failed: boolean } | null>(null);
  const manual = useLocal<Assignment[]>(MANUAL, NONE);
  const done = useLocal<string[]>(DONE, NO_IDS);
  const todos = useLocal<Todo[]>(TODOS, NO_TODOS);
  const [now] = useState(() => new Date());
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const [course, setCourse] = useState("");
  const [date, setDate] = useState("");
  const [time, setTime] = useState("23:59");

  useEffect(() => {
    let live = true;
    apiGet<AssignmentsData>("/assignments")
      .then((data) => live && setRes({ data, failed: false }))
      .catch(() => live && setRes({ data: null, failed: true }));
    return () => void (live = false);
  }, []);

  const all = [...(res?.data?.assignments ?? []), ...manual].sort((a, b) => a.due.localeCompare(b.due));
  const shown = all.filter((a) => new Date(a.due).getTime() > now.getTime() - 86400000);

  function add(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !date) return;
    const due = new Date(`${date}T${time || "23:59"}`).toISOString();
    saveLocal<Assignment[]>(MANUAL, [...manual, { id: `m${Date.now()}`, title: title.trim(), course: course.trim() || null, due, all_day: false, url: null, source: "Gradescope", manual: true }]);
    setTitle("");
    setCourse("");
    setAdding(false);
  }
  const toggle = (id: string) => saveLocal(DONE, done.includes(id) ? done.filter((x) => x !== id) : [...done, id]);

  const feeds = res?.data?.feeds ?? {};
  return (
    <section aria-labelledby="as" className="rounded border border-line p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 id="as" className="text-lg font-semibold">Assignments due</h2>
        <button type="button" onClick={() => setAdding(!adding)} aria-expanded={adding} className="rounded border border-line px-2 py-0.5 text-xs">{adding ? "Cancel" : "+ Add"}</button>
      </div>
      {res?.data?.sample && <p className="mt-1 text-xs text-warn"><span aria-hidden="true">⚠</span> Sample assignments. Add your Blackboard calendar link in backend/.env to see real ones.</p>}
      {res?.failed && <p className="mt-1 text-sm text-warn"><span aria-hidden="true">✕</span> Calendar feeds unavailable (backend offline). Items you add here still show.</p>}
      {Object.entries(feeds).filter(([, s]) => s === "unavailable" || s === "cached").map(([src, s]) => (
        <p key={src} className="mt-1 text-xs text-warn"><span aria-hidden="true">⚠</span> {src}: {s === "cached" ? "could not refresh, showing the last saved copy" : "could not load the calendar link"}.</p>
      ))}

      {adding && (
        <form onSubmit={add} className="mt-2 grid grid-cols-2 gap-2 rounded bg-surface p-2">
          <label className="col-span-2 text-xs">What is due<input required value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Gradescope HW 5" className={`${field} mt-0.5 w-full`} /></label>
          <label className="col-span-2 text-xs">Class (optional)<input value={course} onChange={(e) => setCourse(e.target.value)} placeholder="e.g. CS 111" className={`${field} mt-0.5 w-full`} /></label>
          <label className="text-xs">Date<input required type="date" value={date} onChange={(e) => setDate(e.target.value)} className={`${field} mt-0.5 w-full`} /></label>
          <label className="text-xs">Time<input type="time" value={time} onChange={(e) => setTime(e.target.value)} className={`${field} mt-0.5 w-full`} /></label>
          <button type="submit" className="col-span-2 rounded bg-accent px-3 py-1.5 text-sm font-medium text-white dark:text-black">Save</button>
        </form>
      )}

      {!res && <p className="mt-1 text-sm opacity-70">Loading…</p>}
      {res && shown.length === 0 && <p className="mt-1 text-sm"><span aria-hidden="true">✓</span> Nothing due in the next two weeks.</p>}
      <ul className="mt-2 space-y-2 text-sm">
        {shown.map((a) => {
          const isDone = done.includes(a.id);
          const soon = new Date(a.due).getTime() - now.getTime() < 86400000;
          const inTodo = todos.some((t) => t.id === `a:${a.id}`);
          return (
            <li key={a.id} className="flex items-start gap-2">
              <input type="checkbox" checked={isDone} onChange={() => toggle(a.id)} aria-label={`Mark ${a.title} done`} className="mt-1" />
              <div className={`min-w-0 flex-1 ${isDone ? "line-through opacity-60" : ""}`}>
                <div className="font-medium">{a.url ? <a href={a.url} target="_blank" rel="noreferrer" className="underline">{a.title}</a> : a.title}</div>
                <div className="text-xs opacity-80">
                  <span className={soon && !isDone ? "font-semibold text-warn" : ""}>{dueLabel(a.due, a.all_day, now)}</span>
                  {a.course && <> · {a.course}</>} · <span className="rounded border border-line px-1">{a.source}</span>
                </div>
              </div>
              <div className="flex shrink-0 gap-1">
                <button type="button" disabled={inTodo} onClick={() => addTodo(todos, a.course ? `${a.course}: ${a.title}` : a.title, a.due, `a:${a.id}`)} aria-label={`Add ${a.title} to to-do list`} className="rounded border border-line px-2 py-0.5 text-xs disabled:opacity-50">{inTodo ? "In to-do" : "+ To-do"}</button>
                {a.manual && <button type="button" onClick={() => saveLocal(MANUAL, manual.filter((m) => m.id !== a.id))} aria-label={`Delete ${a.title}`} className="px-1 text-xs">✕</button>}
              </div>
            </li>
          );
        })}
      </ul>
      <p className="mt-2 text-xs opacity-70">Blackboard comes from your calendar link. Gradescope has no calendar link, so add those with “+ Add” (saved in this browser).</p>
    </section>
  );
}
