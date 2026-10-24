# Compass

A BU student manager and schedule optimizer, built as a hackathon prototype. It builds class schedules that avoid tight walks and keep a lunch window, tells you when to leave for class using live shuttle data, finds meal gaps at open dining halls, suggests classes for Hub areas you still need, and exports your week to a calendar.

> **Prototype.** Courses come from the real BU catalog for Spring 2027, but only part of it is listed (see [Course catalog](#course-catalog)), most rooms are not assigned yet, building coordinates are approximate and unverified, and the shuttle delay model trains on synthetic placeholder data until enough real predictions have been logged. Read the in-app **About and limitations** page (or the [Known limitations](#known-limitations) section below) before relying on any output.

## What it does

| Tab | Features |
|---|---|
| **Build** | Search the catalog, mark courses required or optional, set a credit range, earliest start, latest end and walking pace, then generate the top 3 distinct schedules (OR-Tools CP-SAT) shown as weekly grids with metrics and plain-language explanations. A Hub panel suggests courses that cover Hub areas you still need without creating tight transitions or removing a lunch window. |
| **Week** | Your selected schedule with a transition-risk badge on each class (green, amber, red, or unknown, each with an icon), a Leave-By card for your next class, service alerts, `.ics` download, and the friends panel. |
| **Briefing** | One mobile-friendly screen: today's classes, first-class leave-by time, alerts, meal windows and a transit-risk summary. |
| **Eat** | Open dining halls, meal windows that fit your schedule gaps, and dietary filters (vegetarian, vegan, gluten-free, halal). |

Also: onboarding (dorm, required course codes, target credits, completed Hub areas), dark mode, a small animated Boston Terrier pet (sleeping, idle, walking; can be hidden), keyboard navigation and a color-blind-safe palette. Every status uses an icon and text, never color alone.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy + SQLite, OR-Tools CP-SAT, scikit-learn (quantile gradient boosting), APScheduler. Python 3.11+ (developed on 3.12).
- **Frontend:** Next.js (App Router, TypeScript) and Tailwind CSS.
- **Data:** BU API gateway for shuttle and dining data (read-only). Course catalog from a swappable `CatalogSource` interface: the private read-only catalog database (PostgreSQL), with a disk cache and a synthetic sample file as fallbacks.

## Repository layout

```
backend/
  main.py             FastAPI app, CORS, all non-auth routes
  optimizer.py        CP-SAT schedule generator and scoring
  baselines.py        random and greedy baselines
  evaluate.py         optimizer vs baselines, delay-model evaluation -> eval_results.json
  leaveby.py          leave-by times, on-time probability, alerts, schedule store
  delay_model.py      quantile model of shuttle delay (hour, weekday, route, stop)
  transit_logger.py   2-minute background logger -> transit_log table
  transit_net.py      route/stop network and the "watched stops" list
  meals.py            meal-gap finder and dietary filter
  hub.py              Hub gap-filler
  ics.py              .ics export
  social.py           @bu.edu accounts, friend requests, shared free windows
  locations.py        building/dorm lookup, location classification, walking-time helper
  db.py               SQLAlchemy models (SQLite, compass.db)
  clients/
    catalog.py        CatalogSource interface, DbCatalogSource, SampleCatalogSource (fallback)
    catalog_db.py     read-only SELECTs, filtering, Hub/prerequisite parsing, disk cache
    transit.py        BU transit adapter (disk cache, falls back to cache/fixtures)
    dining.py         BU dining adapter (same)
    bu_http.py        shared GET + cache + fallback
  data/sample_catalog.json   SYNTHETIC fallback catalog (~40 fictional courses)
frontend/             Next.js app (app/, components/, lib/)
fixtures/             locations.csv (buildings/dorms) and data-pull output; optional offline fallback files
scripts/              one-off data-pull helpers (see below)
dev.sh                run both servers for development
```

## Getting started

Requirements: Python 3.11+, Node 20+, and a virtualenv at the repo root (`.venv`).

```bash
python3 -m venv .venv                                  # once
cp backend/.env.example backend/.env                   # then fill in BU_BASE / BU_API_KEY and DB_*
cp frontend/.env.example frontend/.env.local           # optional for local dev
./dev.sh                                               # installs deps, starts both servers
```

`dev.sh` loads `backend/.env`, installs `backend/requirements.txt`, runs `npm install` if needed, then starts:

- Backend: <http://localhost:8000> (interactive API docs at `/docs`)
- Frontend: <http://localhost:3000>

Or run them yourself:

```bash
# backend
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn main:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev
```

**The app runs offline.** Without BU credentials, or when the gateway is unreachable, shuttle and dining data fall back to disk cache (`backend/.cache/`), then to files in `fixtures/`, then to "unavailable". The course catalog falls back to its disk copy of the last successful read, and only then to the synthetic sample catalog. The header badges show which sources are live, cached or sample.

## Configuration

Secrets come only from environment variables; never commit real values. See `backend/.env.example` and `frontend/.env.example`.

| Variable | Where | Purpose |
|---|---|---|
| `BU_BASE`, `BU_API_KEY`, `BU_AUTH`, `BU_TOKEN` | backend | BU API gateway address and credentials (`BU_AUTH` = `x-api-key`, `bearer`, `query:<param>` or `none`) |
| `CORS_ORIGINS` | backend | Comma-separated browser origins allowed to call the API (default: `http://localhost:3000,http://127.0.0.1:3000`) |
| `COMPASS_LOGGER` | backend | Set to `0` to turn off the 2-minute transit logger |
| `NEXT_PUBLIC_API_URL` | frontend | Backend URL. Baked in at **build** time |
| `BU_SPEC_URL` | scripts only | Optional OpenAPI spec URL for `scripts/pull_bu_api.py` |
| `DB_ENGINE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL` | backend, scripts | Read-only catalog database (PostgreSQL). The app only runs SELECTs, in a read-only session |
| `CATALOG_TERM` | backend | Term to list: `2271` = Spring 2027 (default), `2268` = Fall 2026 |

## API overview

Interactive docs are at `/docs` when the backend is running. The frontend also has an **About and limitations** page at `/about`.

| Route | Purpose |
|---|---|
| `GET /health`, `GET /data-status` | Liveness; which sources are live, cached or sample |
| `GET /courses?q=&limit=`, `GET /sections?course_id=` | Catalog search (codes match with or without spaces; `limit=0` returns all) and sections |
| `GET /buildings`, `GET /dorms` | Lookup tables |
| `POST /schedules/generate` | Top 3 schedules with metrics, flags and explanations |
| `GET /leave-by?schedule_id=&class_id=` | Leave time, on-time probability, and why |
| `GET /alerts` | Service alerts for your routes (empty list if none) |
| `GET /meals?schedule_id=&day=&diet=` | Meal gaps that fit, with open dining halls |
| `GET /hub/suggestions?schedule_id=&completed=` | Courses covering remaining Hub areas that fit your schedule |
| `GET /export.ics?schedule_id=` | Weekly recurring calendar with leave-by alarms and optional meal windows |
| `POST /watch` | Tells the transit logger which dorm and buildings matter |
| `POST /auth/register`, `/auth/login`, `/auth/logout`, `GET /me`, `POST /me/settings`, `POST /me/schedule` | Optional accounts (`@bu.edu` email, hashed password, bearer session) |
| `POST /friends/request`, `/friends/accept`, `GET /friends`, `GET /friends/free-gaps?friend_id=` | Friends: shared free windows only, never course names |

## Course catalog

All app code talks to the `CatalogSource` interface in `backend/clients/catalog.py`. `DbCatalogSource` reads the BU catalog (schema `catalog`: `courses`, `sections`, `meetings`) with SELECT-only queries in a read-only session, once at startup, and saves a copy to `backend/.cache/catalog_<term>.json` (git-ignored). The header badge shows `live` or `cached`; if neither the database nor a cache exists, the synthetic sample catalog is used and the badge says so.

Only part of the catalog is listed, because the optimizer needs a fixed weekly time for every section:

- Spring 2027 (`2271`), undergraduate, regular full-term session, Charles River campus.
- Class-like section types (lecture, discussion, laboratory and variants) that meet Monday to Friday. In this catalog `Independent` is the ordinary class type, not independent study; real independent study, directed study, applied music and unscheduled sections are left out.
- A section that meets at more than one time (a regular lecture plus an evening session) becomes one record per meeting, linked so the optimizer always chooses them together.
- Courses with zero or fractional credits, and courses where a lab or discussion cannot be placed, are left out.

Things the catalog does not provide: **Hub areas and prerequisites** exist only as free text in the description, so Hub areas are parsed from the sentence "fulfills a single unit in ... BU Hub areas" (latest "Effective" sentence wins) and prerequisites are shown as the description's own text, unchecked. There are **no seat counts**, and **no link between a lecture and its discussion or lab sections**, so a pairing may not be registrable together. Course codes are shown as `CAS MA 123`.

For Spring 2027 most meetings have no room assigned yet (about 84% of timed meetings), so most classes show as location unknown (see below). Set `CATALOG_TERM=2268` for Fall 2026, where rooms are assigned.

## Locations and walking times

Walking time is haversine distance x 1.3 / 1.3 m/s, scaled by your pace setting. Buildings and dorms come from `fixtures/locations.csv` if present (columns `code,name,lat,lon,kind,verified`, optional `campus`; rows without numeric `lat`/`lon` are skipped and count as missing), otherwise from a small synthetic seed in `backend/locations.py`.

- **Approximate:** a section whose building is missing from the table, or whose row is marked unverified (`verified` = `NO`, `0` or `false`) or has no coordinates, still gets a walking estimate, marked approximate.
- **Location unknown:** medical-campus (BUMC) sections, "No Room" sections and timed sections with no building have no walk time. They are excluded from transition-risk, tight-transition and travel calculations, and get no leave-by time or calendar alarm.

## Evaluation

```bash
cd backend && ../.venv/bin/python evaluate.py
```

Runs 50 simulated course requests through the optimizer and two baselines (random valid, greedy first-fit), prints a metrics table, evaluates the delay model with a time-based split (MAE against the posted schedule, plus a calibration check), and writes `eval_results.json`. It always uses the synthetic sample catalog so results are reproducible without the database, and is labelled "evaluated on synthetic sample catalog". There is no separate automated test suite.

## Deployment

```bash
# backend (run ONE worker: the logger runs in-process and the DB and caches are on local disk)
cd backend && ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# frontend (set NEXT_PUBLIC_API_URL first; it is baked into the build)
cd frontend && npm ci && npm run build && npm run start -- -p 3000
```

Set the backend's `CORS_ORIGINS` to the frontend's public URL. **Most endpoints have no login** (only the friends feature does), so a public deployment lets anyone spend your BU API quota through your backend. Put it behind a login, an IP allowlist or rate limiting.

## Scripts

`scripts/` holds one-off data-gathering helpers, run by hand with the relevant environment variables set:

- `pull_bu_api.py`: discovers gateway endpoints and saves trimmed responses to `fixtures/` and full ones to `backend/cache_seed/`.
- `pull_catalog_db.py`: reads the private catalog database (SELECT only) and saves trimmed samples to `fixtures/` and full ones to `backend/cache_seed/`. `find_access.py`, `find_term.py`, `show_terms.py` are read-only helpers for exploring it.
- `build_locations.py`: builds `fixtures/locations.csv` from catalog meetings. Coordinates are a one-time geocoding guess and every row must be verified by hand.

## Privacy

- Your profile, selected schedule, theme and pet choice are stored in your browser (localStorage).
- Generated schedules are also saved on the server (section times and dorm code only) so leave-by, meals and export work.
- Accounts are optional and used only for friends: `@bu.edu` email, optional display name, salted scrypt password hash, hashed session tokens. **Email ownership is not verified.**
- Sharing is opt-in and off by default. Friends see only windows when you are both free, never course names, buildings or grades.

## Known limitations

- **Partial catalog:** only the courses described in [Course catalog](#course-catalog) are listed. Hub areas and prerequisites are parsed from description text and can be wrong or missing; there are no seat counts and no lecture-to-discussion pairing. The sample catalog (fallback only) is fictional.
- **Approximate locations:** most building coordinates are missing or unverified, so many walking times are flagged approximate. Medical-campus, "No Room" and no-building sections show as location unknown.
- **Non-production API:** the BU gateway used is a non-production environment. Dining hours and menus are published for today only, and the gateway has no route-tagged alerts.
- **Small transit sample:** the delay model uses synthetic placeholder delays until at least 500 real trips over 3 days are logged. The gateway publishes no realized arrival time, so the "actual" delay is the last prediction seen before arrival.
- **Dietary info:** may be outdated; confirm with dining staff. There is no allergen data, so allergens cannot be filtered.
- **Not academic advice:** schedules, Hub suggestions and prerequisite notes are planning aids. Confirm with your academic advisor and the official degree audit.
