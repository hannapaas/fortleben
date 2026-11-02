"""The orchestrator: stages in the order of docs/STAGES.md, stop and resume, and the limits.

Every stage writes its outputs to the database before the next starts, so a run can stop
after any stage and resume from the record; the response cache makes a repeated stage free.
"""

import importlib
import json
import traceback

from house import budget, context, events, works
from house.db import dumps
from house.stages import Ctx
from house.stages.common import DEFAULTS

# The pipeline (docs/STAGES.md). Stages 7 and 8 are the two readers and the desk, per chapter.
PIPELINE = "readers-desk"  # recorded in each run's options, so a fixture says which pipeline made it
STAGES = [
    ("parse", "parse"),
    ("parts", "parts"),
    ("first-read", "first_read"),
    ("crux-check", "crux_check"),
    ("bible", "bible"),
    ("draft", "draft"),
    ("readers", "readers"),
    ("desk", "desk"),
    ("final-read", "final_read"),
    ("copy-desk", "copy_desk"),
    ("notes", "notes"),
    ("release", "release"),
]
NAMES = [s for s, _ in STAGES]


class RunFailed(Exception):
    """A stage failed: the run is recorded as failed at that stage and can be resumed from it."""


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
    options = {"pipeline": PIPELINE, **(options or {})}
    work = works.parse(work_id)
    # make sure the work row exists before a run points at it
    conn.execute("INSERT OR IGNORE INTO work (id, aozora_id, title, author) VALUES (?,?,?,?)",
                 (work_id, work.meta["aozora_id"], work.title, work.author))
    if run_id is None and (from_ or only):
        run_id = latest_run(conn, work_id)
    if run_id is None:
        options = {**DEFAULTS, **options}  # recorded with the run, so a resumed run keeps its own set-up
        # A run is priced before it starts and refused if it won't fit: better no translation than
        # one that stops half-way.
        chars = sum(len(p.text) for p in work.translatable())
        est = budget.estimate_run(chars, len(context.chapters(work)), options)
        cap, room = client.budget.run_cap, client.budget.room()
        if not client.replay_only and est > room:
            b = client.budget
            if room >= cap:
                fix = "raise the run's cap (--cap) to run it"
            elif b.daily_cap - b.spent(today=True) <= b.total_cap - b.spent():
                fix = f"today's budget has ${room:.2f} left; raise KEIKAKU_CAP_DAILY or run it tomorrow"
            else:
                fix = f"the total budget has ${room:.2f} left; raise KEIKAKU_CAP_TOTAL to run it"
            raise budget.CapExceeded(f"{work_id}: this run is estimated at ${est:.2f}, more than it can spend. "
                                     f"Nothing was started; {fix}.")
        run_id = new_run(conn, work_id, label, cap, options)
        events.emit(conn, run_id, "house", "run.started", {"work": work_id, "options": options,
                                                           "cap_usd": cap, "estimate_usd": est})
    else:
        stored = conn.execute("SELECT options, cap_usd FROM run WHERE id=?", (run_id,)).fetchone()
        options = {**json.loads(stored["options"] or "{}"), **options}
        if not client.budget.cap_given and stored["cap_usd"]:
            client.budget.run_cap = stored["cap_usd"]  # a resumed run keeps the cap it started with
        conn.execute("UPDATE run SET options=? WHERE id=?", (dumps(options), run_id))

    names = NAMES
    if only:
        names = [only]
    else:
        start = NAMES.index(from_) if from_ else 0
        end = NAMES.index(to) + 1 if to else len(NAMES)
        names = NAMES[start:end]

    ctx = Ctx(conn, client, work, run_id, options)
    plans = [json.loads(r["body"]) for r in conn.execute(
        "SELECT body FROM bible WHERE work_id=? AND kind='parts' ORDER BY version DESC", (work_id,))]
    plan = next((b for b in plans if b.get("run_id") == run_id), None)  # a resumed run keeps its own parts
    work.parts = plan["starts"] if plan else None
    modules = dict(STAGES)
    for name in names:
        ctx.options["_stage"] = name
        events.emit(conn, run_id, "house", "stage.started", {"stage": name})
        spent_before = client.budget.spent(run_id)
        try:
            summary = importlib.import_module(f"house.stages.{modules[name]}").run(ctx) or {}
        except budget.CapExceeded as e:  # the money ran out mid-run: stop, release nothing, say where
            events.emit(conn, run_id, "house", "run.stopped", {"reason": "budget", "stage": name, "detail": str(e)})
            conn.execute("UPDATE run SET status='stopped: budget' WHERE id=?", (run_id,))
            conn.commit()
            raise budget.CapExceeded(f"budget ran out during the {name} stage of run {run_id}. Nothing was released. "
                                     f"Raise the cap and resume with --run {run_id} --from {name}. ({e})") from e
        except Exception as e:  # a stage that fails records it and the run stops there
            events.emit(conn, run_id, "house", "stage.failed", {"stage": name, "error": f"{type(e).__name__}: {e}",
                                                                "trace": traceback.format_exc()[-2000:]})
            conn.execute("UPDATE run SET status='failed' WHERE id=?", (run_id,))
            conn.commit()
            raise RunFailed(f"run {run_id} failed during the {name} stage: {type(e).__name__}: {e}. "
                            f"The House log has the details; resume with --run {run_id} --from {name}.") from e
        spent = client.budget.spent(run_id) - spent_before
        events.emit(conn, run_id, "house", "stage.done", {"stage": name, "spent_usd": round(spent, 5), **summary})
        conn.execute("UPDATE run SET stage=? WHERE id=?", (name, run_id))
        conn.commit()

    final = names[-1] == NAMES[-1]
    conn.execute("UPDATE run SET status=? WHERE id=?", ("done" if final else "paused", run_id))
    events.emit(conn, run_id, "house", "run.done" if final else "run.paused",
                {"after": names[-1], "spent_usd": round(client.budget.spent(run_id), 5)})
    return run_id
