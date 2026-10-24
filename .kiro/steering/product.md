# Compass: BU student manager and schedule optimizer (hackathon, 6h)

Stack: FastAPI (Python 3.11) + SQLite (SQLAlchemy) + OR-Tools CP-SAT + scikit-learn; Next.js (App Router, TypeScript) + Tailwind.
Data: ONLY three external APIs: course catalog, transit, dining. No other data sources, no scraping, no LLM calls.
Sample API responses live in /fixtures. Code against those real shapes. Never invent fields.

Rules:
- Every API client sits behind an adapter that (a) caches responses to disk and (b) falls back to /fixtures if the API fails. The app must always run offline.
- If a field is missing from the real data, degrade gracefully and tell me. Do not fabricate data.
- Anything seeded or synthetic must be labeled "synthetic" in the UI and code.
- Show probabilities and ranges, never false precision. Every flag has a plain-language "why".
- Accessibility: color-blind-safe palette plus icons (not color-only), keyboard navigation, dark mode.
- Privacy: friends see only free time windows, never course names. No grades, no unneeded personal data.
- Be economical: no README, no docs, no extra test suites, no refactors I didn't ask for. Brief responses. Run what you build and fix errors before reporting done.
- After each completed phase, run: git add -A && git commit -m "<short message>"
