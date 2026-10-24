"use client";
import { useState } from "react";
import { API } from "@/lib/api";

export default function IcsButton({ scheduleId }: { scheduleId: string }) {
  const [meals, setMeals] = useState(true);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <a
        href={`${API}/export.ics?schedule_id=${encodeURIComponent(scheduleId)}&meals=${meals}`}
        download="compass-schedule.ics"
        className="rounded bg-accent px-3 py-1.5 text-sm font-medium text-white dark:text-black"
      >
        <span aria-hidden="true">⇩</span> Download .ics
      </a>
      <label className="flex items-center gap-1 text-sm">
        <input type="checkbox" checked={meals} onChange={(e) => setMeals(e.target.checked)} /> Include optional meal windows
      </label>
      <span className="text-xs opacity-70">Weekly repeating events; each class has a leave-by alarm (walking estimate).</span>
    </div>
  );
}
