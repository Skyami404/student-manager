export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Course = { code: string; title: string; credits: number; hub_units: string[]; prerequisites: string[] };
export type Section = {
  id: string; course_code: string; section_label: string; days: string[];
  start: string | null; end: string | null; building_code: string | null; room: string | null;
  seats_open: number | null; component: "lecture" | "lab" | "discussion";
};
export type Dorm = { code: string; name: string; lat: number; lon: number; source: string };
export type SourceState = "live" | "cached" | "sample" | "unavailable";
export type DataStatus = {
  catalog: { status: SourceState; synthetic: boolean; label: string };
  transit: { status: SourceState };
  dining: { status: SourceState };
  locations: { status: SourceState; source: string; synthetic: boolean };
};

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(`${API}${path}`, { signal });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export type Metrics = {
  tight_transitions: number; travel_minutes: number; travel_minutes_range: [number, number];
  dorm_travel_minutes: number; meal_window_days: number; class_days: number; meal_missing_days: string[];
  longest_gap_minutes: number; off_window_minutes: number; credits: number; cost: number;
};
export type Flag = { kind: string; level: "warn" | "info"; why: string };
export type Schedule = {
  rank: number; optimal: boolean; credits: number;
  courses: { code: string; title: string; credits: number; required: boolean }[];
  sections: Section[]; metrics: Metrics; flags: Flag[]; explanation: string;
};
export type GenerateRequest = {
  required: string[]; optional: string[]; min_credits: number; max_credits: number; dorm_id: string | null;
  earliest_start: string; latest_end: string; walking_pace: "slow" | "normal" | "fast";
};
export type GenerateResult = {
  status: "ok" | "infeasible"; reason?: string; note?: string | null; warnings: string[];
  schedules: Schedule[]; synthetic_catalog: boolean; label: string;
};

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
