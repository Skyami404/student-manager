"use client";
import { useEffect, useState } from "react";
import { apiGet, type Course, type Dorm } from "@/lib/api";
import { saveProfile, type Profile } from "@/lib/profile";

export default function Onboarding({ initial, onDone, onCancel }: { initial: Profile | null; onDone: () => void; onCancel?: () => void }) {
  const [dorms, setDorms] = useState<Dorm[] | null>(null);
  const [catalog, setCatalog] = useState<Course[] | null>(null);
  const [dorm, setDorm] = useState(initial?.dormCode ?? "");
  const [codes, setCodes] = useState<string[]>(initial?.requiredCourses ?? []);
  const [target, setTarget] = useState(String(initial?.targetCredits ?? 16));
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const ac = new AbortController();
    apiGet<Dorm[]>("/dorms", ac.signal).then(setDorms).catch(() => !ac.signal.aborted && setDorms([]));
    apiGet<Course[]>("/courses", ac.signal).then(setCatalog).catch(() => {});
    return () => ac.abort();
  }, []);

  const known = new Set((catalog ?? []).map((c) => c.code));
  const norm = (s: string) => s.trim().toUpperCase().replace(/\s+/g, " ");

  function add() {
    const c = norm(draft);
    if (!c) return;
    if (!codes.includes(c)) setCodes([...codes, c]);
    setDraft("");
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    const credits = Number(target);
    if (!dorm) return setError("Pick a dorm.");
    if (!Number.isFinite(credits) || credits < 1 || credits > 200) return setError("Target credits must be between 1 and 200.");
    saveProfile({ dormCode: dorm, requiredCourses: codes, targetCredits: credits });
    onDone();
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-6" aria-labelledby="ob-h">
      <h1 id="ob-h" className="text-xl font-semibold">Set up your profile</h1>
      <p className="text-sm opacity-80">Stored only in this browser (localStorage).</p>

      <div>
        <label htmlFor="dorm" className="block text-sm font-medium">Dorm</label>
        <select id="dorm" value={dorm} onChange={(e) => setDorm(e.target.value)} className="mt-1 w-full rounded border border-line bg-surface p-2">
          <option value="">{dorms === null ? "Loading…" : "Select a dorm"}</option>
          {(dorms ?? []).map((d) => (
            <option key={d.code} value={d.code}>{d.name}</option>
          ))}
        </select>
        {dorms?.length === 0 && <p role="alert" className="mt-1 text-sm text-warn"><span aria-hidden="true">✕</span> Could not load dorms. Is the backend running?</p>}
        {dorms?.[0]?.source === "synthetic-seed" && <p className="mt-1 text-xs opacity-70">Dorm list is a synthetic seed; locations are approximate.</p>}
      </div>

      <fieldset>
        <legend className="text-sm font-medium">Major requirements: required course codes</legend>
        <div className="mt-1 flex gap-2">
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), add())}
            aria-label="Course code"
            placeholder="e.g. MA 101"
            className="flex-1 rounded border border-line bg-surface p-2"
          />
          <button type="button" onClick={add} className="rounded border border-line bg-surface px-3">Add</button>
        </div>
        <ul className="mt-3 space-y-1">
          {codes.map((c) => (
            <li key={c} className="flex items-center justify-between rounded border border-line px-3 py-1.5 text-sm">
              <span>
                <span aria-hidden="true">☐</span> {c}
                {catalog && !known.has(c) && (
                  <span className="ml-2 text-warn"><span aria-hidden="true">⚠</span> not in sample catalog</span>
                )}
              </span>
              <button type="button" onClick={() => setCodes(codes.filter((x) => x !== c))} aria-label={`Remove ${c}`} className="px-2">✕</button>
            </li>
          ))}
          {codes.length === 0 && <li className="text-sm opacity-70">No courses added yet.</li>}
        </ul>
      </fieldset>

      <div>
        <label htmlFor="target" className="block text-sm font-medium">Target credit total</label>
        <input id="target" type="number" min={1} max={200} value={target} onChange={(e) => setTarget(e.target.value)} className="mt-1 w-28 rounded border border-line bg-surface p-2" />
      </div>

      {error && <p role="alert" className="text-sm text-warn"><span aria-hidden="true">⚠</span> {error}</p>}
      <div className="flex gap-2">
        <button type="submit" className="rounded bg-accent px-4 py-2 font-medium text-white dark:text-black">Save</button>
        {onCancel && <button type="button" onClick={onCancel} className="rounded border border-line px-4 py-2">Cancel</button>}
      </div>
    </form>
  );
}
