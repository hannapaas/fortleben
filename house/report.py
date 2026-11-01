"""A run in numbers: cost, calls per stage, notes per reader, and what the desk did with them."""

import json

from house.works import parse


def run_report(conn, run_id: int) -> dict:
    run = conn.execute("SELECT * FROM run WHERE id=?", (run_id,)).fetchone()
    work = parse(run["work_id"])
    chars = sum(len(p.text) for p in work.translatable())
    calls = conn.execute(
        "SELECT stage, model, COUNT(*) n, SUM(cost_usd) live, SUM(list_cost_usd) list FROM call WHERE run_id=? AND ok=1 "
        "GROUP BY stage, model ORDER BY MIN(id)", (run_id,)).fetchall()
    total = sum(c["list"] for c in calls)
    notes = {}
    for q in conn.execute("SELECT raised_by, status FROM query WHERE run_id=? AND owner='desk'", (run_id,)):
        reader = q["raised_by"].removeprefix("reader/")
        notes.setdefault(reader, {}).setdefault(q["status"], 0)
        notes[reader][q["status"]] += 1
    events = lambda t: [json.loads(r["payload"]) for r in conn.execute(  # noqa: E731
        "SELECT payload FROM event WHERE run_id=? AND type=?", (run_id, t))]
    return {
        "run": run_id, "label": run["label"], "options": json.loads(run["options"]),
        "chars": chars, "usd": round(total, 4), "usd_per_1k_chars": round(total / chars * 1000, 4),
        "calls": [{"stage": c["stage"], "model": c["model"], "calls": c["n"], "usd": round(c["list"], 4)} for c in calls],
        "chapters": len(events("desk.done")),
        "notes": notes,
        "disagreements": len(events("disagreement.recorded")),
        "forks": sum(1 for f in events("fork.opened") if f.get("kind") == "readers"),
        "desk_unprompted": sum(1 for e in events("revision.created") if e.get("cause", {}).get("unprompted")),
        "code_flags": [e["check"] for e in events("check.flagged")],
    }
