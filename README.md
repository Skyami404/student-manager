# Compass

A BU student manager and schedule optimizer, built as a hackathon prototype. It builds class schedules that avoid tight walks and keep a lunch window, tells you when to leave for class using live shuttle data, finds meal gaps at open dining halls, suggests classes for Hub areas you still need, tracks assignments, and exports your week to a calendar.

> **Prototype.** Courses come from the real BU catalog for Spring 2027, but only part of it is listed (see [Course catalog](#course-catalog)), most rooms are not assigned yet, building coordinates are approximate and unverified, and the shuttle delay model trains on synthetic placeholder data until enough real predictions have been logged. Read the in-app **About and limitations** page (or [Known limitations](#known-limitations)) before relying on any output.

## Contents

[What it does](#what-it-does) · [Tech stack](#tech-stack) · [Repository layout](#repository-layout) · [Getting started](#getting-started) · [Configuration](#configuration) · [API overview](#api-overview) · [Course catalog](#course-catalog) · [Locations and walking times](#locations-and-walking-times) · [Assignments](#assignments) · [Evaluation](#evaluation) · [Tests and CI](#tests-and-ci) · [Deployment](#deployment) · [Scripts](#scripts) · [Privacy](#privacy) · [Known limitations](#known-limitations) · [Conhtributing](#contributing) · [License](#license)

## What it does

| Tab              | Features                                                                                                                                                                                                                                                                                                                                                                                 |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Build**        | Search the catalog, mark courses required or optional, set a credit range, earliest start, latest end and walking pace, then generate the top 3 distinct schedules (OR-Tools CP-SAT) shown as weekly grids with metrics and plain-language explanations. A Hub panel suggests courses that cover Hub areas you still need without creating tight transitions or removing a lunch window. |
| **Week**         | Your selected schedule with a transition-risk badge on each class (green, amber, red, or unknown, each with an icon), a Leave-By card for your next class, service alerts, `.ics` download, and the friends panel.                                                                                                                                                                       |
| **Briefing**     | One mobile-friendly screen: today's classes, first-class leave-by time, alerts, meal windows and a transit-risk summary.                                                                                                                                                                                                                                                                 |
| **Eat**          | Open dining halls, meal windows that fit your schedule gaps, and dietary filters (vegetarian, vegan, gluten-free, halal).                                                                                                                                                                                                                                                                |
| **Productivity** | Assignments due (from your Blackboard and Gradescope calendar links, plus items you add by hand), a to-do list, and a Pomodoro timer. See [Assignments](#assignments).                                                                                                                                                                                                                   |

Also: onboarding (dorm, required course codes, target credits, completed Hub areas), dark mode, a Boston Terrier that wanders the screen (you can pet or drag him, and hide him; he does not follow your schedule), keyboard navigation and a color-blind-safe palette. Every status uses an icon and text, never color alone.

## Tech stack

- **Languages:** Python 3.12 (3.11+ should work), TypeScript, CSS, Bash.
- **Backend:** FastAPI, Uvicorn, Pydantic, SQLAlchemy, APScheduler, OR-Tools CP-SAT (schedule optimizer), scikit-learn + pandas + numpy (shuttle delay model, quantile gradient boosting).
- **Frontend:** Next.js 16 (App Router, Turbopack, Cache Components), React 19, Tailwind CSS 4. Node 22 recommended; 20.11+ works.
- **Databases:** SQLite for the app's own data (`backend/compass.db`); PostgreSQL for the BU course catalog (read-only, SELECT only).
- **External APIs:** BU API gateway for shuttle (transit) and dining data. Calendar (`.ics`) feeds for assignments, if you provide links.
- **Cloud services:** none. It runs locally; see [Deployment](#deployment).
- **Quality:** pytest, ruff, TypeScript, ESLint, GitHub Actions ([Tests and CI](#tests-and-ci)).

## Repository layout

```
backend/
  main.py             FastAPI app, CORS, most routes
  optimizer.py        CP-SAT schedule generator and scoring
  baselines.py        random and greedy baselines
  evaluate.py         optimizer vs baselines, delay-model evaluation (-> eval_results.json, git-ignored)
  leaveby.py          leave-by times, on-time probability, alerts, schedule store
  delay_model.py      quantile model of shuttle delay (hour, weekday, route, stop)
  transit_logger.py   2-minute background logger -> transit_log table
  transit_net.py      route/stop network and the "watched stops" list
  meals.py            meal-gap finder and dietary filter
  hub.py              Hub gap-filler
  ics.py              .ics export
  assignments.py      assignments due, read from calendar (.ics) feed links
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
  tests/              offline pytest suite
frontend/             Next.js app (app/, components/, lib/, public/)
fixtures/
  locations.csv       buildings and dorms (coordinates unverified)
  catalog_schema.json column list of the catalog database (no data)
  dining_*.json       hand-made DEMO dining halls and menus, shown only when BU dining is unreachable
  _bu_endpoints.txt   gateway endpoints that were discovered
scripts/              one-off data-pull helpers (see Scripts)
.github/workflows/    CI
dev.sh                run both servers for development
```

## Getting started

Requirements: Python 3.11+, Node 20.11+ (`.nvmrc` pins 22), and a virtualenv at the repo root (`.venv`).

```bash
python3 -m venv .venv                                  # once
cp backend/.env.example backend/.env                   # then fill in what you have (see Configuration)
cp frontend/.env.example frontend/.env.local           # optional
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

The browser talks to the API through a same-origin proxy (`/backend/...`, forwarded by Next.js to `BACKEND_URL`), so no CORS setup or public backend port is needed, which also makes it work in GitHub Codespaces.

**The app runs offline.** Without BU credentials, or when the gateway is unreachable, shuttle and dining data fall back to disk cache (`backend/.cache/`), then to files in `fixtures/` (the dining fixtures are hand-made demo data and are labelled as such in the app), then to "unavailable". The course catalog falls back to its disk copy of the last successful read, and only then to the synthetic sample catalog. The header badges show which sources are live, cached or sample.

## Configuration

Secrets come only from environment variables; never commit real values. See `backend/.env.example` and `frontend/.env.example`.

| Variable                                                                         | Where            | Purpose                                                                                                                                         |
| -------------------------------------------------------------------------------- | ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `BU_BASE`, `BU_API_KEY`, `BU_AUTH`, `BU_TOKEN`                                   | backend          | BU API gateway address and credentials (`BU_AUTH` = `x-api-key`, `bearer`, `query:<param>` or `none`)                                           |
| `DB_ENGINE`, `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSL` | backend, scripts | Read-only catalog database (PostgreSQL). The app only runs SELECTs, in a read-only session                                                      |
| `CATALOG_TERM`                                                                   | backend          | Term to list: `2271` = Spring 2027 (default), `2268` = Fall 2026                                                                                |
| `BLACKBOARD_ICS_URL`, `GRADESCOPE_ICS_URL`                                       | backend          | Private calendar links for [Assignments](#assignments). Treat them as secrets                                                                   |
| `CORS_ORIGINS`                                                                   | backend          | Browser origins allowed to call the API directly (default: `http://localhost:3000,http://127.0.0.1:3000`). Not needed with the `/backend` proxy |
| `COMPASS_LOGGER`                                                                 | backend          | Set to `0` to turn off the 2-minute transit logger                                                                                              |
| `BACKEND_URL`                                                                    | frontend         | Where Next.js forwards `/backend/...` (default `http://127.0.0.1:8000`). Baked in at **build** time                                             |
| `NEXT_PUBLIC_API_URL`                                                            | frontend         | Optional. Call a backend directly from the browser instead of using the proxy. Baked in at **build** time                                       |
| `BU_SPEC_URL`                                                                    | scripts only     | Optional OpenAPI spec URL for `scripts/pull_bu_api.py`                                                                                          |

## API overview

Interactive docs are at `/docs` when the backend is running. The frontend also has an **About and limitations** page at `/about`.

| Route                                                                                                     | Purpose                                                                                 |
| --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `GET /health`, `GET /data-status`                                                                         | Liveness; which sources are live, cached or sample                                      |
| `GET /courses?q=&limit=`, `GET /sections?course_id=`                                                      | Catalog search (codes match with or without spaces; `limit=0` returns all) and sections |
| `GET /buildings`, `GET /dorms`                                                                            | Lookup tables                                                                           |
| `POST /schedules/generate`                                                                                | Top 3 schedules with metrics, flags and explanations                                    |
| `GET /leave-by?schedule_id=&class_id=`                                                                    | Leave time, on-time probability, and why                                                |
| `GET /alerts`                                                                                             | Service alerts for your routes (empty list if none)                                     |
| `GET /meals?schedule_id=&day=&diet=`                                                                      | Meal gaps that fit, with open dining halls                                              |
| `GET /hub/suggestions?schedule_id=&completed=`                                                            | Courses covering remaining Hub areas that fit your schedule                             |
| `GET /export.ics?schedule_id=`                                                                            | Weekly recurring calendar with leave-by alarms and optional meal windows                |
| `GET /assignments?days=`                                                                                  | Assignments due soon from your calendar links (a labelled sample list if none are set)  |
| `POST /watch`                                                                                             | Tells the transit logger which dorm and buildings matter                                |
| `POST /auth/register`, `/auth/login`, `/auth/logout`, `GET /me`, `POST /me/settings`, `POST /me/schedule` | Optional accounts (`@bu.edu` email, hashed password, bearer session)                    |
| `POST /friends/request`, `/friends/accept`, `GET /friends`, `GET /friends/free-gaps?friend_id=`           | Friends: shared free windows only, never course names                                   |

## Course catalog

All app code talks to the `CatalogSource` interface in `backend/clients/catalog.py`. `DbCatalogSource` reads the BU catalog (schema `catalog`: `courses`, `sections`, `meetings`) with SELECT-only queries in a read-only session, once at startup, and saves a copy to `backend/.cache/catalog_<term>.json` (git-ignored). The header badge shows `live` or `cached`; if neither the database nor a cache exists, the synthetic sample catalog is used and the badge says so.

Only part of the catalog is listed, because the optimizer needs a fixed weekly time for every section:

- Spring 2027 (`2271`), undergraduate, regular full-term session, Charles River campus.
- Class-like section types (lecture, discussion, laboratory and variants) that meet Monday to Friday. In this catalog `Independent` is the ordinary class type, not independent study; real independent study, directed study, applied music and unscheduled sections are left out.
- A section that meets at more than one time (a regular lecture plus an evening session) becomes one record per meeting, linked so the optimizer always chooses them together.
- Courses with zero or fractional credits, and courses where a lab or discussion cannot be placed, are left out.

Things the catalog does not provide: **Hub areas and prerequisites** exist only as free text in the description, so Hub areas are parsed from the sentence "fulfills a single unit in ... BU Hub areas" (latest "Effective" sentence wins) and prerequisites are shown as the description's own text, unchecked. There are **no seat counts**, and **no link between a lecture and its discussion or lab sections**, so a pairing may not be registrable together. Course codes are shown as `CAS MA 123`.

For Spring 2027 most meetings have no room assigned yet (about 84% of timed meetings), so most classes show as location unknown (see below). Set `CATALOG_TERM=2268` for Fall 2026, where rooms are assigned.

**Catalog data is not in this repository.** `backend/cache_seed/` and `fixtures/catalog_*.json` (written by `scripts/pull_catalog_db.py`) are git-ignored. Only `fixtures/catalog_schema.json`, which lists column names and no data, is tracked. See [CONTRIBUTING.md](CONTRIBUTING.md) about older commits that still contain it.

## Locations and walking times

Walking time is haversine distance x 1.3 / 1.3 m/s, scaled by your pace setting. Buildings and dorms come from `fixtures/locations.csv` if present (columns `code,name,lat,lon,kind,verified`, optional `campus`; rows without numeric `lat`/`lon` are skipped and count as missing), otherwise from a small synthetic seed in `backend/locations.py`.

- **Approximate:** a section whose building is missing from the table, or whose row is marked unverified (`verified` = `NO`, `0` or `false`) or has no coordinates, still gets a walking estimate, marked approximate.
- **Location unknown:** medical-campus (BUMC) sections, "No Room" sections and timed sections with no building have no walk time. They are excluded from transition-risk, tight-transition and travel calculations, and get no leave-by time or calendar alarm.

## Assignments

The Productivity tab lists what is due in the next 14 days from calendar (`.ics`) links, with no logins or API keys:

- **Blackboard:** Calendar, then Settings, then Share calendar gives a private link. Put it in `BLACKBOARD_ICS_URL`.
- **Gradescope** has no calendar link of its own. Put any `.ics` link that carries your Gradescope due dates in `GRADESCOPE_ICS_URL`, or add items by hand in the app (saved in your browser).
- Each link is a secret (anyone holding it can read your calendar). It lives only in `backend/.env`, and is never returned by the API or logged. Fallback order per feed is live, then disk cache, then skipped.
- With no link set, a small list of clearly labelled sample assignments is shown so the demo has content.

## Evaluation

```bash
cd backend && ../.venv/bin/python evaluate.py
```

Runs 50 simulated course requests through the optimizer and two baselines (random valid, greedy first-fit), prints a metrics table, evaluates the delay model with a time-based split (MAE against the posted schedule, plus a calibration check), and writes `backend/eval_results.json` (git-ignored). It always uses the synthetic sample catalog so results are reproducible without the database, and is labelled "evaluated on synthetic sample catalog".

Latest run (synthetic sample catalog, 50 requests, seed 42; metrics averaged over the 39 requests where all three methods found a valid schedule):

| method           | valid | tight transitions | travel min/week | meal-window days | class days |
| ---------------- | ----- | ----------------- | --------------- | ---------------- | ---------- |
| optimizer        | 48/50 | 0                 | 138.1           | 4.23             | 4.23       |
| random valid     | 48/50 | 0                 | 148.8           | 4.56             | 4.62       |
| greedy first-fit | 39/50 | 0                 | 146.3           | 4.49             | 4.54       |

The optimizer walks less than both baselines and finds a valid schedule wherever one exists; greedy first-fit fails when it cannot backtrack. Every schedule it returns is re-scored independently of the solver and the two costs match.

Shuttle delay model, trained on **synthetic** delays (0 real trips logged, 500 trips over 3 days are needed to switch to real data): median MAE 106 s vs 140 s for the posted schedule (95% bootstrap interval for the improvement: 30 to 37 s), and the 80% prediction interval covers 77% of test delays. This shows the pipeline works on a pattern we invented, not real shuttle accuracy.

## Tests and CI

```bash
.venv/bin/pip install -r backend/requirements-dev.txt
.venv/bin/ruff check backend scripts
.venv/bin/pytest
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

The 55 backend tests run offline (no database, network or API keys; `conftest.py` blanks those variables before anything is imported). They cover the catalog parsers and filters, location classification, the optimizer (including linked meetings and unknown locations), calendar export, leave-by helpers, the delay model on synthetic data and the assignments feed parser. The same commands run in GitHub Actions on every push to `main` and every pull request (`.github/workflows/ci.yml`).

## Deployment

```bash
# backend (run ONE worker: the logger runs in-process and the DB and caches are on local disk)
cd backend && ../.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# frontend (set BACKEND_URL first if the API is not on the same machine; it is baked into the build)
cd frontend && npm ci && npm run build && npm run start -- -p 3000
```

With the default `/backend` proxy the browser only ever talks to the frontend. If you set `NEXT_PUBLIC_API_URL` instead, set the backend's `CORS_ORIGINS` to the frontend's public URL.

**Most endpoints have no login** (only the friends feature does), so a public deployment lets anyone spend your BU API quota through your backend. Schedule generation is also CPU-heavy, and the solver time limit and request size are not capped. Put the backend behind a login, an IP allowlist or rate limiting before exposing it.

## Scripts

`scripts/` holds one-off data-gathering helpers, run by hand with the relevant environment variables set. Their output goes to git-ignored paths:

- `pull_bu_api.py`: discovers gateway endpoints and saves responses under `fixtures/` and `backend/cache_seed/`.
- `pull_catalog_db.py`: reads the private catalog database (SELECT only) and saves samples under `fixtures/` and full copies under `backend/cache_seed/`. `find_access.py`, `find_term.py`, `show_terms.py` are read-only helpers for exploring it.
- `build_locations.py`: builds `fixtures/locations.csv` from catalog meetings. Coordinates are a one-time geocoding guess and every row must be verified by hand.

## Privacy

- Your profile, selected schedule, theme, pet choice, to-do items and Pomodoro timer are stored in your browser (localStorage).
- Generated schedules are also saved on the server (section times and dorm code only) so leave-by, meals and export work.
- Accounts are optional and used only for friends: `@bu.edu` email, optional display name, salted scrypt password hash, hashed session tokens. **Email ownership is not verified.**
- Sharing is opt-in and off by default. Friends see only windows when you are both free, never course names, buildings or grades.
- Calendar links for assignments are secrets kept in `backend/.env` and never returned or logged.

## Known limitations

- **Partial catalog:** only the courses described in [Course catalog](#course-catalog) are listed. Hub areas and prerequisites are parsed from description text and can be wrong or missing; there are no seat counts and no lecture-to-discussion pairing. The sample catalog (fallback only) is fictional.
- **Approximate locations:** most building coordinates are missing or unverified, so many walking times are flagged approximate. Medical-campus, "No Room" and no-building sections show as location unknown.
- **Non-production API:** the BU gateway used is a non-production environment. Dining hours and menus are published for today only, and the gateway has no route-tagged alerts. When dining is unreachable the app shows hand-made demo halls and menus, labelled as examples.
- **Small transit sample:** the delay model uses synthetic placeholder delays until at least 500 real trips over 3 days are logged. The gateway publishes no realized arrival time, so the "actual" delay is the last prediction seen before arrival.
- **Saved schedules:** the server keeps only the 100 most recent generated schedules. An older one stops working for leave-by, meals and export until you generate it again.
- **Dietary info:** may be outdated; confirm with dining staff. There is no allergen data, so allergens cannot be filtered.
- **Not academic advice:** schedules, Hub suggestions and prerequisite notes are planning aids. Confirm with your academic advisor and the official degree audit.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the checks CI runs, and the commit-message style.

## License

No license has been chosen yet, so by default all rights are reserved. Add a `LICENSE` file before accepting outside contributions or making the repository public.
