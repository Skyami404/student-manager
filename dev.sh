#!/usr/bin/env bash
cd "$(dirname "$0")" || exit 1

[ -d .venv ] || { echo "No .venv found. Run: python3 -m venv .venv"; exit 1; }
source .venv/bin/activate

if [ -f backend/.env ]; then set -a; source backend/.env; set +a; fi

ENTRY=$(grep -rl "FastAPI(" backend --include=*.py 2>/dev/null | head -1)
[ -n "$ENTRY" ] || { echo "No FastAPI app found in backend/"; exit 1; }
MODULE=$(echo "${ENTRY#backend/}" | sed 's/\.py$//; s#/#.#g')
echo "Backend entry: $MODULE:app"

[ -f backend/requirements.txt ] && pip install -q -r backend/requirements.txt
[ -d frontend/node_modules ] || (cd frontend && npm install)

trap 'trap - EXIT INT TERM; kill 0' EXIT INT TERM

(cd backend && uvicorn "$MODULE:app" --reload --port 8000) &
(cd frontend && npm run dev) &

echo "Backend:  http://localhost:8000/docs"
echo "Frontend: http://localhost:3000"
wait