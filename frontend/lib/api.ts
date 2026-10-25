export const API = process.env.NEXT_PUBLIC_API_URL ?? "/backend";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json() as Promise<T>;
}

export type Course = {
  code: string;
  title: string;
  credits: number;
  hub_units: string[];
  prerequisites: string[];
};
export type Section = {
  id: string;
  course_code: string;
  section_label: string;
  days: string[];
  start: string | null;
  end: string | null;
  building_code: string | null;
  room: string | null;
  seats_open: number | null;
  component: "lecture" | "lab" | "discussion";
  /** ok | approximate | unknown | n/a. "unknown" = no building, "No Room", or medical campus (no walk time). */
  location_status?: "ok" | "approximate" | "unknown" | "n/a";
  location_reason?: string | null;
};
export type Dorm = {
  code: string;
  name: string;
  lat: number;
  lon: number;
  source: string;
};
export type SourceState = "live" | "cached" | "sample" | "unavailable";
export type DataStatus = {
  catalog: { status: SourceState; synthetic: boolean; label: string; term?: string | null; as_of?: string | null };
  transit: { status: SourceState };
  dining: { status: SourceState };
  locations: {
    status: SourceState;
    source: string;
    synthetic: boolean;
    approximate?: boolean;
    buildings_in_table?: number;
    buildings_verified?: number;
  };
  delay_model?: {
    source: "real" | "synthetic";
    synthetic: boolean;
    real_trips: number;
    note: string;
  };
};

export async function apiGet<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const r = await fetch(`${API}${path}`, { signal });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export type Transition = {
  day: string;
  from_section: string;
  to_section: string;
  from_building: string | null;
  to_building: string | null;
  gap_minutes: number;
  walk_minutes: number | null;
  tight: boolean;
  p_on_time: number | null;
  risk: "green" | "amber" | "red" | "unknown";
  risk_why: string;
  approximate?: boolean;
  location_unknown?: boolean;
};
export type Metrics = {
  transitions: Transition[];
  tight_transitions: number;
  travel_minutes: number;
  travel_minutes_range: [number, number];
  dorm_travel_minutes: number;
  meal_window_days: number;
  class_days: number;
  meal_missing_days: string[];
  longest_gap_minutes: number;
  off_window_minutes: number;
  credits: number;
  cost: number;
  approximate?: boolean;
  unknown_transitions?: number;
  unknown_location_sections?: string[];
};
export type Flag = { kind: string; level: "warn" | "info"; why: string };
export type Schedule = {
  id: string;
  rank: number;
  optimal: boolean;
  credits: number;
  courses: {
    code: string;
    title: string;
    credits: number;
    required: boolean;
  }[];
  sections: Section[];
  metrics: Metrics;
  flags: Flag[];
  explanation: string;
};
export type GenerateRequest = {
  required: string[];
  optional: string[];
  min_credits: number;
  max_credits: number;
  dorm_id: string | null;
  earliest_start: string;
  latest_end: string;
  walking_pace: "slow" | "normal" | "fast";
};
export type GenerateResult = {
  status: "ok" | "infeasible";
  reason?: string;
  note?: string | null;
  warnings: string[];
  schedules: Schedule[];
  synthetic_catalog: boolean;
  label: string;
};

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

export type LeaveBy = {
  class_id: string;
  course_code: string;
  day: string;
  class_start: string;
  leave_at: string | null;
  leave_at_iso: string | null;
  mode: "walk" | "bus" | "unknown";
  location_unknown?: boolean;
  approximate?: boolean;
  probability_on_time: number | null;
  probability_label: string | null;
  destination: string;
  why: string;
  warnings: string[];
  origin: { kind: "dorm" | "class"; code: string } | null;
  bus: {
    route_id: string;
    board_stop: string;
    alight_stop: string;
    scheduled_departure: string;
    gateway_eta: string | null;
  } | null;
  delay_model: { source: string; synthetic: boolean } | null;
};
export type AlertItem = {
  kind: string;
  route_specific: boolean;
  text: string;
  why: string;
  at?: string;
  url?: string;
};
export type Alerts = {
  alerts: AlertItem[];
  routes: string[];
  notes: string[];
  note_no_route_alerts: string;
};

export type MealOption = {
  hall_id: string;
  hall: string;
  meal: string;
  walk_to_min: number;
  walk_from_min: number;
  start_between: [string, string];
  matching_items: number | null;
  total_items: number | null;
  examples: string[];
  open_now: boolean | null;
};
export type MealGap = {
  kind: "before_first" | "between" | "after_last";
  start: string;
  end: string;
  minutes: number;
  fits: boolean | null;
  location_unknown?: boolean;
  options: MealOption[];
  why: string;
};
export type Hall = {
  id: string;
  name: string;
  short_name: string;
  campus: string;
  address: string;
  open_now: boolean | null;
  status_text: string | null;
  meals: {
    meal: string;
    opens_at: string;
    closes_at: string;
    matching_items: number | null;
    total_items: number | null;
  }[];
};
export type Meals = {
  day: string;
  hours_source: "today" | "last_observed" | "unavailable";
  hours_date: string | null;
  data_status: string;
  diet: string[];
  diet_filters_available: { id: string; label: string }[];
  allergen_filter: { available: boolean; reason: string };
  disclaimer: string;
  allergy_notice: string;
  halls: Hall[];
  gaps: MealGap[];
  notes: string[];
  meal_minutes: number;
};
export type HubSuggestion = {
  course: {
    code: string;
    title: string;
    credits: number;
    hub_units: string[];
    prerequisites: string[];
  };
  covers: string[];
  location_unknown?: boolean;
  sections: Section[];
  after: {
    tight_transitions: number;
    meal_window_days: number;
    class_days: number;
    added_travel_minutes: number;
    credits: number;
  };
  why: string;
};
export type HubResult = {
  hub_units: string[];
  completed: string[];
  covered_by_schedule: string[];
  remaining: string[];
  suggestions: HubSuggestion[];
  total_found: number;
  rejected_courses: Record<string, number>;
  label: string;
};

/** Authenticated JSON call; throws Error(message) using the server's detail text when available. */
export async function authApi<T>(
  method: "GET" | "POST",
  path: string,
  token: string | null,
  body?: unknown,
): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method,
    headers: {
      ...(body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok)
    throw new Error(
      typeof j.detail === "string"
        ? j.detail
        : (j.detail?.[0]?.msg ?? `Request failed (${r.status})`),
    );
  return j as T;
}
export type Me = {
  id: number;
  email: string;
  display_name: string | null;
  share_free_time: boolean;
  has_schedule: boolean;
  email_verified: boolean;
};
export type FriendRow = {
  id: number;
  display_name: string | null;
  email: string;
  shares_free_time: boolean;
};
export type FriendsData = {
  friends: FriendRow[];
  incoming: (FriendRow & { request_id: number })[];
  outgoing: { request_id: number; email: string }[];
  note: string;
};
export type FreeGaps = {
  friend: { id: number; display_name: string | null };
  windows: Record<string, { start: string; end: string; minutes: number }[]>;
  privacy: string;
};
