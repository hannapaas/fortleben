"""The SQLite database: one file, schema from db/schema.sql."""

import json
import os
import sqlite3
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "db" / "schema.sql"


def data_dir() -> Path:
    """Where everything a run makes is kept: the database, the response cache, audits and releases.
    KEIKAKU_DATA_DIR (from the environment or .env; on Railway, the volume), else the repo's var/."""
    d = os.environ.get("KEIKAKU_DATA_DIR") or dotenv_values(ROOT / ".env").get("KEIKAKU_DATA_DIR")
    return Path(d) if d else ROOT / "var"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(path) if path else data_dir() / "keikaku.db"
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
