"use client";
import AssignmentsCard from "@/components/AssignmentsCard";
import PomodoroCard from "@/components/PomodoroCard";
import TodoCard from "@/components/TodoCard";
import { useNow } from "@/lib/schedule";

export default function ProductivityPage() {
  // null during prerender: the cards read the clock, so they only render in the browser.
  const now = useNow();
  return (
    <section aria-labelledby="h" className="mx-auto max-w-xl space-y-4">
      <h1 id="h" className="text-xl font-semibold">Productivity</h1>
      {!now ? (
        <p className="text-sm opacity-70">Loading…</p>
      ) : (
        <>
          <AssignmentsCard />
          <TodoCard />
          <PomodoroCard />
        </>
      )}
    </section>
  );
}
