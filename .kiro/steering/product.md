# Compass: BU student manager and schedule optimizer (hackathon, 6h)

Stack: FastAPI (Python 3.11) + SQLite (SQLAlchemy) + OR-Tools CP-SAT + scikit-learn; Next.js (App Router, TypeScript) + Tailwind.
Python: use the existing virtualenv at the project root (.venv). Install backend deps into it and keep backend/requirements.txt updated. Do not create another venv.

Data:
- Transit and dining come from the BU API gateway (REST). Read /fixtures for real response shapes. Never invent fields.
- Course catalog: the real source is a private read-only SQL database that is NOT reachable yet. Code only against the CatalogSource interface (backend/clients/catalog.py). The current implementation reads backend/data/sample_catalog.json, which is SYNTHETIC. Label it "Sample data" in the UI and code. A DbCatalogSource will be added later by me. Do not write SQL against guessed tables.
- No other data sources, no scraping, no LLM calls. Never write to any external database.
- Do not open backend/cache_seed.

Rules:
- Every external client caches to disk and falls back to cached or sample data on failure. The app must always run offline.
- If a field is missing from real data, degrade gracefully and tell me. Do not fabricate real-looking data.
- Anything seeded or synthetic must be labeled "synthetic" in the UI and code.
- Show probabilities and ranges, never false precision. Every flag has a plain-language "why".
- Accessibility: color-blind-safe palette plus icons (not color-only), keyboard navigation, dark mode.
- Privacy: friends see only free time windows, never course names. No grades, no unneeded personal data.
- Secrets only from env vars. Never hardcode or print them.
- Be economical: no README, no docs, no extra test suites, no refactors I didn't ask for. Brief responses. Run what you build and fix errors before reporting done.
- After each completed phase: git add -A && git commit -m "<short message>"
