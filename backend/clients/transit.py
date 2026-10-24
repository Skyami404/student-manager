"""BU bus transit adapter. Paths from fixtures/_bu_endpoints.txt.

No response fixtures exist yet, so responses are returned as raw JSON: no field names are
assumed. Add typed parsing once real shapes are available in /fixtures.
Each function returns (data | None, status) with status live|cached|sample|unavailable.
"""
from urllib.parse import quote

from .bu_http import fetch

PREFIX = "/api/v1/transit/bus"


def routes():
    return fetch("transit", f"{PREFIX}/routes")


def vehicles():
    return fetch("transit", f"{PREFIX}/vehicles")


def arrivals(stop_id: str):
    return fetch("transit", f"{PREFIX}/stops/{quote(stop_id, safe='')}/arrivals")


def notices():
    return fetch("transit", f"{PREFIX}/notices")
