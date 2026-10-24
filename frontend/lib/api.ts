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
