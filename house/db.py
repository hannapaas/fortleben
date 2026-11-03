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
    _migrate(conn)
    return conn


# Columns added to tables after databases with them already existed: CREATE TABLE IF NOT EXISTS
# leaves an old table as it was, so these are added here, once.
ADDED = {"person": {"api_key": "TEXT", "key_tail": "TEXT", "email": "TEXT", "password_hash": "TEXT",
                    "created_at": "TEXT"},
         "work": {"language": "TEXT NOT NULL DEFAULT 'ja'", "title_en": "TEXT", "author_en": "TEXT",
                  "blurb": "TEXT", "added_by": "INTEGER"},
         "edition": {"accent": "TEXT"}}


def _migrate(conn: sqlite3.Connection) -> None:
    for table, cols in ADDED.items():
        have = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        for col, kind in cols.items():
            if col not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {kind}")
    # After the columns, so an old person table has its email column first.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS person_email ON person(email)")
    conn.commit()


def dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)
