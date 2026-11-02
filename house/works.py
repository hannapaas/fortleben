"""The works the house knows, their rights records, and their stored sources."""

import json
from pathlib import Path

from house.lang.ja import aozora
from house.parser import ParsedWork

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "fixtures" / "works.json"
SOURCES = ROOT / "fixtures" / "sources"


def registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def info(work_id: str) -> dict:
    works = registry()
    if work_id not in works:
        raise KeyError(f"unknown work {work_id!r}; known: {', '.join(works)}")
    return works[work_id]


def eligible(rights: dict) -> bool:
    """The hackathon rule: the author died ≤1931 and the work was published ≤1930,
    or the record says why a later death is used (docs/CONVENTIONS.md, "Rights")."""
    died = rights.get("author_died") or 9999
    pub = rights.get("first_published_year")
    if died <= 1931 and pub is not None and pub <= 1930:
        return True
    return died <= 1938 and "strong reason" in rights.get("verdict", "")


def source_path(work_id: str) -> Path:
    return SOURCES / f"{work_id}.txt"


def fetch(work_id: str) -> Path:
    w = info(work_id)
    if not eligible(w["rights"]):
        raise PermissionError(f"{work_id} doesn't pass the rights record")
    text = aozora.fetch(w["zip_url"]).replace("\r\n", "\n")
    if w.get("chapter"):  # a dev text taken from one chapter of a longer work
        text = aozora.chapter(text, w["chapter"])
    SOURCES.mkdir(parents=True, exist_ok=True)
    path = source_path(work_id)
    path.write_text(text, encoding="utf-8")
    return path


def parse(work_id: str) -> ParsedWork:
    w = info(work_id)
    return aozora.parse(source_path(work_id).read_text(encoding="utf-8"), meta={"work_id": work_id, **w})
