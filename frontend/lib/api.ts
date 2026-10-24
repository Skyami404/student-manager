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
  delay_model?: { source: "real" | "synthetic"; synthetic: boolean; real_trips: number; note: string };
};

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(`${API}${path}`, { signal });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export type Transition = {
  day: string; from_section: string; to_section: string; from_building: string | null; to_building: string | null;
  gap_minutes: number; walk_minutes: number; tight: boolean; p_on_time: number; risk: "green" | "amber" | "red"; risk_why: string;
};
export type Metrics = {
  transitions: Transition[];
  tight_transitions: number; travel_minutes: number; travel_minutes_range: [number, number];
  dorm_travel_minutes: number; meal_window_days: number; class_days: number; meal_missing_days: string[];
  longest_gap_minutes: number; off_window_minutes: number; credits: number; cost: number;
};
export type Flag = { kind: string; level: "warn" | "info"; why: string };
export type Schedule = {
  id: string; rank: number; optimal: boolean; credits: number;
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

export type LeaveBy = {
  class_id: string; course_code: string; day: string; class_start: string; leave_at: string; mode: "walk" | "bus";
  probability_on_time: number; probability_label: string; destination: string; why: string; warnings: string[];
  origin: { kind: "dorm" | "class"; code: string };
  bus: { route_id: string; board_stop: string; alight_stop: string; scheduled_departure: string; gateway_eta: string | null } | null;
  delay_model: { source: string; synthetic: boolean } | null;
};
export type AlertItem = { kind: string; route_specific: boolean; text: string; why: string; at?: string; url?: string };
export type Alerts = { alerts: AlertItem[]; routes: string[]; notes: string[]; note_no_route_alerts: string };

export type MealOption = { hall_id: string; hall: string; meal: string; walk_to_min: number; walk_from_min: number; start_between: [string, string];
  matching_items: number | null; total_items: number | null; examples: string[]; open_now: boolean | null };
export type MealGap = { kind: "before_first" | "between" | "after_last"; start: string; end: string; minutes: number; fits: boolean; options: MealOption[]; why: string };
export type Hall = { id: string; name: string; short_name: string; campus: string; address: string; open_now: boolean | null; status_text: string | null;
  meals: { meal: string; opens_at: string; closes_at: string; matching_items: number | null; total_items: number | null }[] };
export type Meals = {
  day: string; hours_source: "today" | "last_observed" | "unavailable"; hours_date: string | null; data_status: string; diet: string[];
  diet_filters_available: { id: string; label: string }[]; allergen_filter: { available: boolean; reason: string };
  disclaimer: string; allergy_notice: string; halls: Hall[]; gaps: MealGap[]; notes: string[]; meal_minutes: number;
};
export type HubSuggestion = { course: { code: string; title: string; credits: number; hub_units: string[]; prerequisites: string[] }; covers: string[];
  sections: Section[]; after: { tight_transitions: number; meal_window_days: number; class_days: number; added_travel_minutes: number; credits: number }; why: string };
export type HubResult = { hub_units: string[]; completed: string[]; covered_by_schedule: string[]; remaining: string[];
  suggestions: HubSuggestion[]; total_found: number; rejected_courses: Record<string, number>; label: string };
