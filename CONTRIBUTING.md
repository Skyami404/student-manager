# Contributing

## Setup

```bash
python3 -m venv .venv                                 # Python 3.12 (see .python-version)
.venv/bin/pip install -r backend/requirements-dev.txt
cp backend/.env.example backend/.env                  # fill in what you have; the app also runs offline
cd frontend && npm ci                                 # Node 22 (see .nvmrc); 20.11+ works
./dev.sh                                              # from the repo root: starts both servers
```

## Before you open a PR

These are the same checks CI runs:

```bash
.venv/bin/ruff check backend scripts                  # unused imports, undefined names
.venv/bin/pytest                                      # offline: no database, network or API keys needed
cd frontend && npx tsc --noEmit && npm run lint && npm run build
```

## Rules of thumb

- **Never commit secrets or private data.** `backend/.env`, `backend/.cache/`, `backend/cache_seed/` and
  `fixtures/catalog_*.json` are git-ignored on purpose. Add new variables to the matching `.env.example`.
- **The app must keep working offline.** External sources cache to disk and fall back; keep it that way.
- **Label synthetic or demo data** wherever it is shown, and prefer ranges and a plain-language "why" over false precision.
- Keep accessibility intact: status is never conveyed by color alone, and everything works from the keyboard.
- Keep changes focused. Unrelated reformatting makes reviews hard.

## Commit messages

Short, imperative, capitalised summary line (about 70 characters), for example `Add Hub gap-filler endpoint`
or `Fix leave-by time when the previous class is unknown`. Put the reason in the body when it is not obvious.
Avoid summaries like `update` or `fix`. Do not rewrite shared history without agreeing it with the team first.

## Private data in git history

`backend/cache_seed/` and `fixtures/catalog_*.json` (pulls from the private catalog database) are no longer tracked, but earlier
commits still contain them. If the repository will ever be shared outside the team, remove them from history first. This rewrites
history, so agree it with everyone, make a backup clone, and have everyone re-clone afterwards:

```bash
pip install git-filter-repo
git clone --mirror git@github.com:OWNER/REPO.git compass-purge && cd compass-purge
git filter-repo --invert-paths --path backend/cache_seed/ \
  --path-regex '^fixtures/catalog_(catalog\.)?(courses|sections|meetings|terms|dataset_info)\.json$'
git push --force --mirror
```

`fixtures/catalog_schema.json` (column names only) is deliberately kept. GitHub may keep cached copies of old commits and pull-request
refs until it garbage-collects them; contact GitHub support if that matters.

If you pull the commit that stopped tracking these files, git deletes your local copies of them. Back them up first, or regenerate
them with `scripts/pull_catalog_db.py`.
