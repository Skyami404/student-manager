"""BU dining adapter. Paths from fixtures/_bu_endpoints.txt.

No response fixtures exist yet, so responses are returned as raw JSON: no field names are
assumed. Add typed parsing once real shapes are available in /fixtures.
Each function returns (data | None, status) with status live|cached|sample|unavailable.
"""
from urllib.parse import quote

from .bu_http import fetch

PREFIX = "/api/v1/dining"


def locations():
    return fetch("dining", f"{PREFIX}/locations")


def menu(location: str):
    return fetch("dining", f"{PREFIX}/locations/{quote(location, safe='')}/menu")


def menu_item(location: str, item_id: str):
    return fetch("dining", f"{PREFIX}/locations/{quote(location, safe='')}/menu/items/{quote(item_id, safe='')}")
