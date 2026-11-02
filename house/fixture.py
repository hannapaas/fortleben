"""Export a recorded run to fixtures/<work>/: every model response (so FakeClient can replay the
run with no key) and the run's record as JSON (so the site and House lanes can build on it).

fixtures/<work>/run.json holds the work, its paragraphs, the latest reading, crux check, bible and
parts, every revision, query, fork and note, the full event log, and the spend ledger
(model, effort, tokens, cost, prompt and input hashes) for every call. Nothing is edited by hand.
"""

import json
import shutil
from pathlib import Path

from house.client import FIXTURES, cache_dir

TABLES = {
    "segment": "SELECT * FROM segment WHERE work_id=:work ORDER BY seq",
    "bible": "SELECT * FROM bible b WHERE work_id=:work AND version=(SELECT MAX(version) FROM bible WHERE work_id=b.work_id AND kind=b.kind) ORDER BY kind",
    "revision": "SELECT * FROM revision WHERE run_id=:run ORDER BY id",
    "query": "SELECT * FROM query WHERE run_id=:run ORDER BY id",
    "fork": "SELECT * FROM fork WHERE run_id=:run ORDER BY id",
    "note": "SELECT * FROM note WHERE run_id=:run ORDER BY id",
    "status": "SELECT * FROM status WHERE work_id=:work ORDER BY segment_id",
    "event": "SELECT * FROM event WHERE run_id=:run ORDER BY seq",
    "call": "SELECT * FROM call WHERE run_id=:run AND ok=1 ORDER BY id",
}
JSON_COLUMNS = {
    "segment": {"tokens", "sentences"}, "bible": {"body"}, "revision": {"segment_ids", "spans", "notes", "alternatives", "flags"},
    "query": {"evidence", "answer"}, "fork": {"options"}, "note": {"editions", "sources"}, "event": {"payload"},
    "work": {"rights"}, "run": {"options"},
}


def rows(conn, table: str, sql: str, args: dict) -> list[dict]:
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        for k in JSON_COLUMNS.get(table, set()) & d.keys():
            if isinstance(d[k], str):
                d[k] = json.loads(d[k])
        out.append(d)
    return out


def export(conn, work_id: str, run_id: int) -> Path:
    dest = FIXTURES / work_id
    responses = dest / "responses"
    responses.mkdir(parents=True, exist_ok=True)
    args = {"work": work_id, "run": run_id}
    record = {"work": rows(conn, "work", "SELECT * FROM work WHERE id=:work", args)[0],
              "run": rows(conn, "run", "SELECT * FROM run WHERE id=:run", args)[0]}
    record.update({name: rows(conn, name, sql, args) for name, sql in TABLES.items()})
    for c in record["call"]:
        src = cache_dir() / f"{c['response_key']}.json"
        if src.exists():
            shutil.copy(src, responses / src.name)
    release = conn.execute("SELECT body FROM release WHERE run_id=? ORDER BY id DESC LIMIT 1", (run_id,)).fetchone()
    if release:
        record["release"] = json.loads(release["body"])
    record["totals"] = {
        "calls": len(record["call"]),
        "live_cost_usd": round(sum(c["list_cost_usd"] for c in record["call"]), 4),
        "by_prompt": {},
    }
    for c in record["call"]:
        b = record["totals"]["by_prompt"].setdefault(c["prompt"], {"calls": 0, "usd": 0.0})
        b["calls"] += 1
        b["usd"] = round(b["usd"] + c["list_cost_usd"], 4)
    (dest / "run.json").write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    return dest
