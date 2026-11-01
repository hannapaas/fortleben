"""The orchestrator: stages in the order of docs/STAGES.md, stop and resume, and the limits.

Every stage writes its outputs to the database before the next starts, so a run can stop
after any stage and resume from the record; the response cache makes a repeated stage free.
"""

import importlib
import json
import traceback

from house import events, works
from house.db import dumps
from house.stages import Ctx

# The minimal pipeline (docs/STAGES.md): 0, 2, 4, 6, 7, 9, 12 (code), 13, 16; plus 3, the crux check.
STAGES = [
    ("parse", "parse"),
    ("first-read", "first_read"),
    ("crux-check", "crux_check"),
    ("bible", "bible"),
    ("draft", "draft"),
    ("source-check", "source_check"),
    ("answer", "answer"),
    ("copy-desk", "copy_desk"),
    ("notes", "notes"),
    ("release", "release"),
]
NAMES = [s for s, _ in STAGES]


def new_run(conn, work_id: str, label: str | None, cap: float | None, options: dict) -> int:
    cur = conn.execute("INSERT INTO run (work_id, label, cap_usd, options) VALUES (?,?,?,?)",
                       (work_id, label, cap, dumps(options)))
    conn.commit()
    return cur.lastrowid


def latest_run(conn, work_id: str) -> int | None:
    row = conn.execute("SELECT id FROM run WHERE work_id=? ORDER BY id DESC LIMIT 1", (work_id,)).fetchone()
    return row["id"] if row else None


def run(conn, client, work_id: str, *, to: str | None = None, from_: str | None = None,
        only: str | None = None, run_id: int | None = None, label: str | None = None,
        options: dict | None = None) -> int:
    options = options or {}
    work = works.parse(work_id)
    # make sure the work row exists before a run points at it
    conn.execute("INSERT OR IGNORE INTO work (id, aozora_id, title, author) VALUES (?,?,?,?)",
                 (work_id, work.meta["aozora_id"], work.title, work.author))
    if run_id is None and (from_ or only):
        run_id = latest_run(conn, work_id)
    if run_id is None:
        run_id = new_run(conn, work_id, label, client.budget.run_cap, options)
        events.emit(conn, run_id, "house", "run.started", {"work": work_id, "options": options,
                                                           "cap_usd": client.budget.run_cap})
    else:
        stored = conn.execute("SELECT options FROM run WHERE id=?", (run_id,)).fetchone()
        options = {**json.loads(stored["options"] or "{}"), **options}

    names = NAMES
    if only:
        names = [only]
    else:
        start = NAMES.index(from_) if from_ else 0
        end = NAMES.index(to) + 1 if to else len(NAMES)
        names = NAMES[start:end]

    ctx = Ctx(conn, client, work, run_id, options)
    modules = dict(STAGES)
    for name in names:
        ctx.options["_stage"] = name
        events.emit(conn, run_id, "house", "stage.started", {"stage": name})
        spent_before = client.budget.spent(run_id)
        try:
            summary = importlib.import_module(f"house.stages.{modules[name]}").run(ctx) or {}
        except Exception as e:  # a stage that fails records it and the run stops there
            events.emit(conn, run_id, "house", "stage.failed", {"stage": name, "error": f"{type(e).__name__}: {e}",
                                                                "trace": traceback.format_exc()[-2000:]})
            conn.execute("UPDATE run SET status='failed' WHERE id=?", (run_id,))
            conn.commit()
            raise
        spent = client.budget.spent(run_id) - spent_before
        events.emit(conn, run_id, "house", "stage.done", {"stage": name, "spent_usd": round(spent, 5), **summary})
        conn.execute("UPDATE run SET stage=? WHERE id=?", (name, run_id))
        conn.commit()

    final = names[-1] == NAMES[-1]
    conn.execute("UPDATE run SET status=? WHERE id=?", ("done" if final else "paused", run_id))
    events.emit(conn, run_id, "house", "run.done" if final else "run.paused",
                {"after": names[-1], "spent_usd": round(client.budget.spent(run_id), 5)})
    return run_id
