"""The works keikaku knows, their rights records, and their stored sources.

Two lists, read in this order: the repo's fixtures/works.json (with texts in fixtures/sources/), and
works people have added from an Aozora link (house/acquire.py), kept in the `work` table with their
texts in the data folder's sources/. Added works have ids starting `aozora-`. Code with a database
connection passes it and sees both; without one, only the repo's list.
"""

import json
from pathlib import Path

from house.db import data_dir
from house.lang.ja import aozora
from house.parser import ParsedWork

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "fixtures" / "works.json"
SOURCES = ROOT / "fixtures" / "sources"
ADDED = "aozora-"  # the id prefix of a work added from a link: aozora-<author id>-<card number>


def registry(conn=None) -> dict:
    works = json.loads(REGISTRY.read_text(encoding="utf-8"))
    if conn is not None:
        for wid, w in added(conn).items():
            works.setdefault(wid, w)
    return works


def added(conn) -> dict:
    """The works added from Aozora links, in the shape of works.json's entries, oldest first."""
    out = {}
    for r in conn.execute("SELECT * FROM work WHERE id LIKE ? AND status = 'parsed' ORDER BY created_at, id", (ADDED + "%",)):
        out[r["id"]] = {"aozora_id": r["aozora_id"], "author_id": r["author_id"], "title": r["title"],
                        "title_en": r["title_en"], "author": r["author"], "author_en": r["author_en"],
                        "card_url": r["card_url"], "zip_url": r["source_url"], "blurb": r["blurb"],
                        "language": r["language"], "rights": json.loads(r["rights"] or "{}"), "added": True}
    return out


def info(work_id: str, conn=None) -> dict:
    works = registry(conn)
    if work_id not in works:
        raise KeyError(f"unknown work {work_id!r}; known: {', '.join(works)}")
    return works[work_id]


def eligible(rights: dict) -> bool:
    """The rights rule: the author died ≤1931 and the work was published ≤1930,
    or the record says why a later death is used (docs/CONVENTIONS.md, "Rights")."""
    died = rights.get("author_died") or 9999
    pub = rights.get("first_published_year")
    if died <= 1931 and pub is not None and pub <= 1930:
        return True
    return died <= 1938 and "strong reason" in rights.get("verdict", "")


def source_path(work_id: str) -> Path:
    if work_id.startswith(ADDED):
        return data_dir() / "sources" / f"{work_id}.txt"
    return SOURCES / f"{work_id}.txt"


def fetch(work_id: str) -> Path:
    """Fetch a work in fixtures/works.json into fixtures/sources. (An added work's text is fetched when it's added.)"""
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


def parse(work_id: str, conn=None) -> ParsedWork:
    w = info(work_id, conn)
    return aozora.parse(source_path(work_id).read_text(encoding="utf-8"), meta={"work_id": work_id, **w})
