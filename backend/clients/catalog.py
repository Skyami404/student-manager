"""Internal catalog format + CatalogSource interface.

All app code talks to CatalogSource only. SampleCatalogSource reads SYNTHETIC data;
DbCatalogSource (stub) will be filled in later against the real read-only database.
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


class CatalogSource(ABC):
    synthetic: bool
    label: str

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
        self.label = raw.get("label", "Sample data (synthetic)")
        self._courses = [Course(**c) for c in raw["courses"]]
        self._sections = [Section(**s) for s in raw["sections"]]

    def courses(self) -> list[Course]:
        return self._courses

    def sections(self) -> list[Section]:
        return self._sections


class DbCatalogSource(CatalogSource):
    """Stub for the real private, read-only SQL catalog database (not reachable yet).

    Must map, READ-ONLY, from the real schema to:
      Course:  code ("DEPT NNN" form), title, credits (int), hub_units (list of Hub area
               names), prerequisites (list of course codes)
      Section: id (stable unique string), course_code, section_label, days (Mon..Fri list),
               start/end ("HH:MM" 24h; None if TBA/online), building_code (must match
               codes in the buildings lookup table), room, seats_open (None if unknown),
               component (lecture | lab | discussion)
    Set synthetic = False once implemented. Never write to the external database.
    """

    synthetic = False
    label = "Course catalog database"

    def courses(self) -> list[Course]:
        raise NotImplementedError("DbCatalogSource: map real catalog tables to Course")

    def sections(self) -> list[Section]:
        raise NotImplementedError("DbCatalogSource: map real catalog tables to Section")


def get_catalog_source() -> CatalogSource:
    return SampleCatalogSource()
