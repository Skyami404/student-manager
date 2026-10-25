"use client";
import { useState } from "react";
import { TODOS, addTodo, saveLocal, useLocal, type Todo } from "@/lib/local";

const NO_TODOS: Todo[] = [];

export default function TodoCard() {
  const todos = useLocal<Todo[]>(TODOS, NO_TODOS);
  const [text, setText] = useState("");
  const left = todos.filter((t) => !t.done).length;

  function submit(e: React.FormEvent) {
    e.preventDefault();
    addTodo(todos, text);
    setText("");
  }
  const update = (id: string, patch: Partial<Todo> | null) =>
    saveLocal<Todo[]>(TODOS, patch ? todos.map((t) => (t.id === id ? { ...t, ...patch } : t)) : todos.filter((t) => t.id !== id));

  return (
    <section aria-labelledby="td" className="rounded border border-line p-4">
      <h2 id="td" className="text-lg font-semibold">To-do <span className="text-sm font-normal opacity-70">· {left} left</span></h2>
      <form onSubmit={submit} className="mt-2 flex gap-2">
        <label htmlFor="todo-new" className="sr-only">New to-do</label>
        <input id="todo-new" value={text} onChange={(e) => setText(e.target.value)} placeholder="Add a task…" className="min-w-0 flex-1 rounded border border-line bg-surface p-1.5 text-sm" />
        <button type="submit" className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white dark:text-black">Add</button>
      </form>
      {todos.length === 0 && <p className="mt-2 text-sm opacity-70">No tasks yet. Type one above, or press “+ To-do” on an assignment.</p>}
      <ul className="mt-2 space-y-1 text-sm">
        {todos.map((t) => (
          <li key={t.id} className="flex items-center gap-2">
            <input type="checkbox" checked={t.done} onChange={() => update(t.id, { done: !t.done })} aria-label={`Mark ${t.text} done`} />
            <span className={`flex-1 ${t.done ? "line-through opacity-60" : ""}`}>{t.text}</span>
            <button type="button" onClick={() => update(t.id, null)} aria-label={`Delete ${t.text}`} className="px-1 text-xs">✕</button>
          </li>
        ))}
      </ul>
      {todos.some((t) => t.done) && (
        <button type="button" onClick={() => saveLocal(TODOS, todos.filter((t) => !t.done))} className="mt-2 text-xs underline">Clear finished</button>
      )}
    </section>
  );
}
