"""Internal catalog format + CatalogSource interface.

All app code talks to CatalogSource only. DbCatalogSource reads the real BU catalog from the read-only database;
SampleCatalogSource reads SYNTHETIC data and is only the fallback when neither the database nor its cache exists.
"""
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

Component = Literal["lecture", "lab", "discussion"]


class Course(BaseModel):
    code: str                      # e.g. "MA 101"
    title: str
    credits: int
    hub_units: list[str] = []
    prerequisites: list[str] = []  # course codes


class Section(BaseModel):
    id: str
    course_code: str
    section_label: str
    days: list[str] = []           # "Mon".."Fri"; empty for TBA/online
    # Spec says "HH:MM"; None for TBA/online sections (no meeting time exists).
    start: str | None = None
    end: str | None = None
    building_code: str | None = None
    room: str | None = None
    seats_open: int | None = None  # None = unknown
    component: Component = "lecture"
    # A section that meets at more than one time/place is stored as one record per meeting. The extra records
    # point at the main one (this holds its id) and are always chosen together with it.
    linked_to: str | None = None


class CatalogSource(ABC):
    synthetic: bool
    label: str
    status: str = "live"        # live | cached | sample
    as_of: str | None = None    # when the underlying data was last refreshed (real catalog only)

    @abstractmethod
    def courses(self) -> list[Course]: ...

    @abstractmethod
    def sections(self) -> list[Section]: ...


SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_catalog.json"


class SampleCatalogSource(CatalogSource):
    """Reads backend/data/sample_catalog.json. SYNTHETIC: fictional courses."""

    def __init__(self, path: Path = SAMPLE_PATH):
        raw = json.loads(Path(path).read_text())
        self.synthetic = bool(raw.get("synthetic", True))
        self.status = "sample"
        self.label = raw.get("label", "Sample data (synthetic)")
        self._courses = [Course(**c) for c in raw["courses"]]
        self._sections = [Section(**s) for s in raw["sections"]]

    def courses(self) -> list[Course]:
        return self._courses

    def sections(self) -> list[Section]:
        return self._sections


class CatalogUnavailable(RuntimeError):
    pass


class DbCatalogSource(CatalogSource):
    """The real BU course catalog, read from the private READ-ONLY database (see clients/catalog_db.py for exactly
    what is listed and how the free-text Hub areas and prerequisites are parsed). Falls back to a disk copy of the
    last successful read when the database is unreachable; raises CatalogUnavailable if there is neither."""

    synthetic = False

    def __init__(self, term: str | None = None):
        from clients.catalog_db import load_snapshot  # imported here: catalog_db imports this module

        got = load_snapshot(term)
        if got is None:
            raise CatalogUnavailable("catalog database unreachable and no disk cache")
        snap, self.status = got
        self.term_label = snap["term_label"]
        self.label = f"BU course catalog, {self.term_label}"
        self.as_of = snap.get("as_of")
        self.stats = snap.get("stats", {})
        self._courses = [Course(**c) for c in snap["courses"]]
        self._sections = [Section(**s) for s in snap["sections"]]

    def courses(self) -> list[Course]:
        return self._courses

    def sections(self) -> list[Section]:
        return self._sections


def get_catalog_source() -> CatalogSource:
    """Real catalog (live database, else its disk cache); the SYNTHETIC sample catalog only as a last resort,
    so the app always starts offline. The sample is labelled as such wherever it is shown."""
    try:
        return DbCatalogSource()
    except CatalogUnavailable:
        return SampleCatalogSource()
