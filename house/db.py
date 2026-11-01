"""The SQLite database: one file, schema from db/schema.sql."""

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"
DEFAULT_DB = ROOT / "var" / "keikaku.db"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path) if path else DEFAULT_DB
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
