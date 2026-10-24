"use client";
import { useEffect, useState } from "react";
import { apiGet, type Course, type Section } from "@/lib/api";
import { useProfile } from "@/lib/profile";

function meeting(s: Section) {
  return s.days.length ? `${s.days.join("/")} ${s.start}–${s.end} · ${s.building_code ?? "?"} ${s.room ?? ""}` : "TBA / online";
}

function Sections({ code }: { code: string }) {
  const [rows, setRows] = useState<Section[] | null>(null);
  useEffect(() => {
    apiGet<Section[]>(`/sections?course_id=${encodeURIComponent(code)}`).then(setRows).catch(() => setRows([]));
  }, [code]);
  if (!rows) return <p className="text-sm opacity-70">Loading sections…</p>;
  return (
    <ul className="mt-2 space-y-1 text-sm">
      {rows.map((s) => (
        <li key={s.id} className="flex flex-wrap gap-x-3">
          <span className="font-medium">{s.section_label}</span>
          <span className="capitalize">{s.component}</span>
          <span>{meeting(s)}</span>
          <span>
            {s.seats_open === 0 ? <><span aria-hidden="true">✕</span> Full</> : s.seats_open === null ? "Seats unknown" : <><span aria-hidden="true">✓</span> {s.seats_open} seats open</>}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function BuildPage() {
  const { profile } = useProfile();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Course[] | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    const t = setTimeout(() => {
      apiGet<Course[]>(`/courses?q=${encodeURIComponent(q)}`, ac.signal).then(setResults).catch(() => !ac.signal.aborted && setResults([]));
    }, 200);
    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [q]);

  return (
    <section aria-labelledby="h" className="space-y-4">
      <h1 id="h" className="text-xl font-semibold">Build</h1>
      {profile && (
        <p className="text-sm opacity-80">
          Target: {profile.targetCredits} credits · {profile.requiredCourses.length} required course(s)
        </p>
      )}
      <div>
        <label htmlFor="q" className="block text-sm font-medium">Search courses (sample catalog)</label>
        <input id="q" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Code or title, e.g. calculus" className="mt-1 w-full max-w-md rounded border border-line bg-surface p-2" />
      </div>
      <p aria-live="polite" className="text-sm opacity-70">{results ? `${results.length} course(s)` : "Loading…"}</p>
      <ul className="space-y-2">
        {(results ?? []).map((c) => (
          <li key={c.code} className="rounded border border-line p-3">
            <button type="button" onClick={() => setOpen(open === c.code ? null : c.code)} aria-expanded={open === c.code} className="w-full text-left">
              <span className="font-medium">{c.code}</span> · {c.title} · {c.credits} cr
              {c.hub_units.length > 0 && <span className="ml-2 text-xs opacity-80">Hub: {c.hub_units.join(", ")}</span>}
            </button>
            {c.prerequisites.length > 0 && <p className="text-xs opacity-70">Prereqs: {c.prerequisites.join(", ")}</p>}
            {open === c.code && <Sections code={c.code} />}
          </li>
        ))}
      </ul>
    </section>
  );
}
