"use client";
import { useEffect, useState } from "react";
import { apiGet, type HubResult } from "@/lib/api";
import { useProfile } from "@/lib/profile";
import { useSelected } from "@/lib/selected";

export default function HubPanel({ maxCredits }: { maxCredits: number }) {
  const { profile } = useProfile();
  const sel = useSelected();
  const done = profile?.completedHub ?? [];
  const sid = sel?.schedule.id;
  const key = `${sid}|${done.join(",")}|${maxCredits}`;
  const [res, setRes] = useState<{ key: string; data: HubResult | null }>({ key: "", data: null });
  const [err, setErr] = useState(false);

  useEffect(() => {
    if (!sid) return;
    let live = true;
    const q = new URLSearchParams({ schedule_id: sid, max_credits: String(maxCredits) });
    done.forEach((d) => q.append("completed", d));
    apiGet<HubResult>(`/hub/suggestions?${q}`)
      .then((data) => live && (setRes({ key, data }), setErr(false)))
      .catch(() => live && setErr(true));
    return () => void (live = false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const data = sid && res.key === key ? res.data : null;
  const total = data?.hub_units.length;

  return (
    <section aria-labelledby="hub" className="rounded border border-line p-4">
      <h2 id="hub" className="text-lg font-semibold">Hub tracker <span className="text-xs font-normal opacity-70">(suggestions may add up to 4 credits above your max)</span></h2>
      {!sid && <p className="mt-1 text-sm">Choose “Use this schedule” on a result to see Hub suggestions that fit it. Completed areas: {done.length} (edit in Edit profile).</p>}
      {err && <p role="alert" className="mt-1 text-sm text-warn"><span aria-hidden="true">✕</span> Could not load Hub suggestions.</p>}
      {sid && !data && !err && <p className="mt-1 text-sm opacity-70">Loading…</p>}
      {data && (
        <div className="mt-2 space-y-3 text-sm">
          <p>
            <span aria-hidden="true">{data.remaining.length === 0 ? "✓" : "◐"}</span>{" "}
            {data.completed.length} of {total} areas done · {data.covered_by_schedule.length} covered by this schedule · {data.remaining.length} still needed
          </p>
          {data.remaining.length > 0 && <p className="text-xs opacity-80">Still needed: {data.remaining.join(", ")}</p>}
          {data.suggestions.length === 0 && data.remaining.length > 0 && (
            <p><span aria-hidden="true">ℹ</span> No course fits this schedule without overlaps, tight transitions, or losing a lunch window (rejected: {Object.entries(data.rejected_courses).filter(([, n]) => n).map(([k, n]) => `${k.replace(/_/g, " ")} ${n}`).join(", ") || "none"}).</p>
          )}
          <ul className="space-y-2">
            {data.suggestions.map((s) => (
              <li key={s.course.code} className="rounded border border-line p-2">
                <div className="font-medium">{s.course.code} · {s.course.title} · {s.course.credits} cr</div>
                <div className="text-xs"><span aria-hidden="true">✓</span> Covers: {s.covers.join(", ")}</div>
                {s.location_unknown && <div className="text-xs font-medium"><span aria-hidden="true">? </span>Location unknown: walking can&apos;t be checked for this one</div>}
                <ul className="mt-1 text-xs">
                  {s.sections.map((x) => (
                    <li key={x.id}>{x.component} {x.section_label}: {x.days.length ? `${x.days.join("/")} ${x.start}–${x.end} · ${x.location_status === "unknown" ? "location unknown" : x.building_code}` : "TBA / online"}{x.seats_open !== null && x.seats_open <= 5 ? ` · ${x.seats_open} seats left` : ""}</li>
                  ))}
                </ul>
                <p className="mt-1 text-xs opacity-80">{s.why}</p>
              </li>
            ))}
          </ul>
          <p className="text-xs opacity-60">{data.label}. Suggestions are checked against this schedule only; confirm prerequisites and degree rules.</p>
        </div>
      )}
    </section>
  );
}
