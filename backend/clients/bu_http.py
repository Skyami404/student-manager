"""Shared BU gateway GET with disk cache and fallback. Secrets come from env vars only.

Fallback order: live -> disk cache (backend/.cache) -> fixtures/ file -> unavailable.
Status values: live | cached | sample (fixture) | unavailable.
(backend/cache_seed is intentionally never read.)
"""
import json
import os
import re
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
CACHE_DIR = ROOT / ".cache"
FIXTURES = ROOT.parent / "fixtures"

LAST_STATUS: dict[str, str] = {}  # topic -> status of the most recent call


def _auth() -> tuple[dict, dict]:
    key, token, mode = os.environ.get("BU_API_KEY", ""), os.environ.get("BU_TOKEN", ""), os.environ.get("BU_AUTH", "x-api-key")
    if token:
        return {"Authorization": f"Bearer {token}"}, {}
    if not key or mode == "none":
        return {}, {}
    if mode == "bearer":
        return {"Authorization": f"Bearer {key}"}, {}
    if mode.startswith("query:"):
        return {}, {mode.split(":", 1)[1]: key}
    return {mode: key}, {}


def _slug(path: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")


def fetch(topic: str, path: str, timeout: float = 5.0) -> tuple[object | None, str]:
    """GET {BU_BASE}{path}. Returns (json_or_None, status). Never raises."""
    slug = _slug(path)
    cache = CACHE_DIR / f"{slug}.json"
    base = os.environ.get("BU_BASE", "").rstrip("/")
    if base:
        headers, params = _auth()
        try:
            r = requests.get(base + path, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            CACHE_DIR.mkdir(exist_ok=True)
            cache.write_text(json.dumps(data))
            LAST_STATUS[topic] = "live"
            return data, "live"
        except (requests.RequestException, ValueError):
            pass  # fall through to cache; never log request details (may contain secrets)
    for p, status in ((cache, "cached"), (FIXTURES / f"{topic}_{slug}.json", "sample")):
        if p.exists():
            try:
                data = json.loads(p.read_text())
            except ValueError:
                continue
            LAST_STATUS[topic] = status
            return data, status
    LAST_STATUS[topic] = "unavailable"
    return None, "unavailable"
