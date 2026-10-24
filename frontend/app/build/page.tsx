"use client";
import { useEffect, useState } from "react";
import HubPanel from "@/components/HubPanel";
import ScheduleResults from "@/components/ScheduleResults";
import {
  apiGet,
  apiPost,
  type Course,
  type GenerateResult,
  type Schedule,
} from "@/lib/api";
import { saveSelected, useSelected } from "@/lib/selected";
import { useProfile } from "@/lib/profile";

const field = "mt-1 rounded border border-line bg-surface p-2";

export default function BuildPage() {
  const { profile } = useProfile();
  const selected = useSelected();
  const [required, setRequired] = useState<string[]>(
    () => profile?.requiredCourses ?? [],
  );
  const [optional, setOptional] = useState<string[]>([]);
  const [minCr, setMinCr] = useState(
    Math.max(1, (profile?.targetCredits ?? 16) - 2),
  );
  const [maxCr, setMaxCr] = useState(profile?.targetCredits ?? 16);
  const [earliest, setEarliest] = useState("09:00");
  const [latest, setLatest] = useState("18:00");
  const [pace, setPace] = useState<"slow" | "normal" | "fast">("normal");
  const [q, setQ] = useState("");
  const [results, setResults] = useState<Course[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [out, setOut] = useState<GenerateResult | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    const t = setTimeout(() => {
      apiGet<Course[]>(`/courses?q=${encodeURIComponent(q)}`, ac.signal)
        .then(setResults)
        .catch(() => !ac.signal.aborted && setResults([]));
    }, 200);
    return () => {
      clearTimeout(t);
      ac.abort();
    };
  }, [q]);

  const add = (code: string, kind: "req" | "opt") => {
    setRequired((r) => r.filter((c) => c !== code));
    setOptional((o) => o.filter((c) => c !== code));
    (kind === "req" ? setRequired : setOptional)((l) => [...l, code]);
  };

  async function generate() {
    setError("");
    if (required.length === 0)
      return setError("Add at least one required course.");
    if (minCr > maxCr)
      return setError("Minimum credits cannot exceed maximum credits.");
    setBusy(true);
    try {
      setOut(
        await apiPost<GenerateResult>("/schedules/generate", {
          required,
          optional,
          min_credits: minCr,
          max_credits: maxCr,
          dorm_id: profile?.dormCode ?? null,
          earliest_start: earliest,
          latest_end: latest,
          walking_pace: pace,
        }),
      );
    } catch {
      setError("Could not generate schedules. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  async function use(s: Schedule) {
    saveSelected({ schedule: s, dormId: profile?.dormCode ?? null });
    // tell the backend which dorm/buildings matter so the transit logger watches the right stops
    const codes = [
      ...new Set(
        s.sections.map((x) => x.building_code).filter((c): c is string => !!c),
      ),
    ];
    apiPost("/watch", {
      dorm_id: profile?.dormCode ?? null,
      building_codes: codes,
    }).catch(() => {});
  }

  const chips = (list: string[], set: (l: string[]) => void, title: string) => (
    <div>
      <h2 className="text-sm font-medium">
        {title} ({list.length})
      </h2>
      <ul className="mt-1 flex flex-wrap gap-1">
        {list.map((c) => (
          <li
            key={c}
            className="flex items-center rounded-full border border-line bg-surface pl-3 text-sm"
          >
            {c}
            <button
              type="button"
              aria-label={`Remove ${c}`}
              onClick={() => set(list.filter((x) => x !== c))}
              className="px-2 py-1"
            >
              ✕
            </button>
          </li>
        ))}
        {list.length === 0 && <li className="text-sm opacity-70">None</li>}
      </ul>
    </div>
  );

  return (
    <section aria-labelledby="h" className="space-y-6">
      <h1 id="h" className="text-xl font-semibold">
        Build
      </h1>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <label htmlFor="q" className="block text-sm font-medium">
            Search courses (sample catalog)
          </label>
          <input
            id="q"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Code or title, e.g. calculus"
            className={`${field} w-full`}
          />
          <p aria-live="polite" className="mt-1 text-xs opacity-70">
            {results ? `${results.length} course(s)` : "Loading…"}
          </p>
          <ul className="mt-2 max-h-80 space-y-1 overflow-y-auto">
            {(results ?? []).map((c) => (
              <li
                key={c.code}
                className="rounded border border-line p-2 text-sm"
              >
                <div>
                  <span className="font-medium">{c.code}</span> · {c.title} ·{" "}
                  {c.credits} cr
                </div>
                {c.hub_units.length > 0 && (
                  <div className="text-xs opacity-70">
                    Hub: {c.hub_units.join(", ")}
                  </div>
                )}
                <div className="mt-1 flex gap-2">
                  <button
                    type="button"
                    onClick={() => add(c.code, "req")}
                    aria-label={`Add ${c.code} as required`}
                    className="rounded border border-line px-2 py-0.5 text-xs"
                  >
                    + Required
                  </button>
                  <button
                    type="button"
                    onClick={() => add(c.code, "opt")}
                    aria-label={`Add ${c.code} as optional`}
                    className="rounded border border-line px-2 py-0.5 text-xs"
                  >
                    + Optional
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="space-y-4">
          {chips(required, setRequired, "Required")}
          {chips(
            optional,
            setOptional,
            "Optional (used if credits are needed)",
          )}
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <label>
              Min credits
              <input
                type="number"
                min={1}
                max={40}
                value={minCr}
                onChange={(e) => setMinCr(Number(e.target.value))}
                className={`${field} w-full`}
              />
            </label>
            <label>
              Max credits
              <input
                type="number"
                min={1}
                max={40}
                value={maxCr}
                onChange={(e) => setMaxCr(Number(e.target.value))}
                className={`${field} w-full`}
              />
            </label>
            <label>
              Walking pace
              <select
                value={pace}
                onChange={(e) => setPace(e.target.value as typeof pace)}
                className={`${field} w-full`}
              >
                <option value="slow">Slow</option>
                <option value="normal">Normal</option>
                <option value="fast">Fast</option>
              </select>
            </label>
            <label>
              Earliest start
              <input
                type="time"
                value={earliest}
                onChange={(e) => setEarliest(e.target.value)}
                className={`${field} w-full`}
              />
            </label>
            <label>
              Latest end
              <input
                type="time"
                value={latest}
                onChange={(e) => setLatest(e.target.value)}
                className={`${field} w-full`}
              />
            </label>
          </div>
          <p className="text-xs opacity-70">
            Dorm: {profile?.dormCode ?? "not set"} (change via Edit profile)
          </p>
          <button
            type="button"
            onClick={generate}
            disabled={busy}
            className="rounded bg-accent px-4 py-2 font-medium text-white disabled:opacity-60 dark:text-black"
          >
            {busy ? "Generating…" : "Generate schedules"}
          </button>
          {error && (
            <p role="alert" className="text-sm text-warn">
              <span aria-hidden="true">⚠</span> {error}
            </p>
          )}
        </div>
      </div>

      <HubPanel maxCredits={maxCr + 4} />

      <div aria-live="polite">
        {out && (
          <ScheduleResults
            result={out}
            selectedId={selected?.schedule.id}
            onUse={use}
          />
        )}
      </div>
    </section>
  );
}
