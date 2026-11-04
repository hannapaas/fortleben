"""Stage 13: notes, one call per part, on the finished English. The keikaku test, after the fansub joke
about a note explaining that "keikaku means plan": only what the sentence can't give the reader. Notes are
the house's and never voiced as the author (Japanese Copyright Act art. 60; docs/REFERENCES.md). They are
stored as unverified.

Each call also sees, for its part, the readers' notes the desk declined and the places the two readers
pulled opposite ways: the road not taken, which a curious reader may want a note on when it's about the text."""

import json
import re

from house import context
from house.client import SPARK, Call, load_schema
from house.db import dumps
from house.stages.common import latest_english, stable, translator_notes

ACTOR = "notes"


def run(ctx) -> dict:
    english = latest_english(ctx)
    done = {json.loads(r["payload"]).get("part") for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='note.written'", (ctx.run_id,))}
    written = 0
    for paras in context.chapters(ctx.work):
        if paras[0].id in done:
            continue
        body = "\n\n".join(
            f"{p.id}　{p.model_text.strip('　 ')}\n{p.id}　{english.get(p.id, '')}"
            + "".join(f"\n  translator's note: {n}" for n in translator_notes(ctx, p.id)) for p in paras)
        inp = context.join(stable(ctx, paras), context.block("The part, Japanese and English", body),
                           road_not_taken(ctx.conn, ctx.run_id, [p.id for p in paras]))
        res = ctx.call(ACTOR, Call("notes", SPARK, "low", inp, load_schema("notes"), f"{ctx.cache_key()}:notes",
                                   expected_output_tokens=2500))
        ids = {p.id for p in paras}
        for n in res.data["notes"]:
            if n["anchor"].split("-")[0] not in ids:
                continue
            cur = ctx.conn.execute(
                "INSERT INTO note (run_id, work_id, anchor, span, editions, body, sources, status, author) VALUES (?,?,?,?,?,?,?,?,?)",
                (ctx.run_id, ctx.work_id, n["anchor"], n["span"], dumps(n["editions"]), n["body"],
                 dumps(n["sources"]), "unverified", ACTOR))
            eid = ctx.emit(ACTOR, "note.written", {"note_id": cur.lastrowid, "part": paras[0].id, **n},
                           call_id=res.call_id)
            ctx.conn.execute("UPDATE note SET event_id=? WHERE id=?", (eid, cur.lastrowid))
            written += 1
        if not res.data["notes"]:  # mark the page done even when it needs no notes
            ctx.emit(ACTOR, "note.written", {"part": paras[0].id, "none": True}, call_id=res.call_id)
        ctx.conn.commit()
    return {"notes": written}


ROAD = "What the readers raised and the desk declined, and where they disagreed"
SIDES = {"reader/faithful": "a reader comparing it with the Japanese", "reader/readable": "a reader of the English alone"}
DECLINED = re.compile(r"^\s*declined[.:]?\s*", re.I)  # the desk sometimes opens its reason with the word


def _first_id(anchor: str) -> str:
    """p12 from p12, p12-s3 or a group p21–p23."""
    return (anchor or "").split("–")[0].split("-")[0].strip()


def road_not_taken(conn, run_id: int, ids: list[str]) -> str:
    """The part's declined notes and recorded disagreements as plain lines, in paragraph order; '' when
    there are none, so the block is left out."""
    order = {pid: i for i, pid in enumerate(ids)}
    rows = []
    for q in conn.execute("SELECT * FROM query WHERE run_id=? AND status='declined' ORDER BY id", (run_id,)):
        pid = _first_id(q["segment_id"])
        if pid not in order:
            continue
        answer = json.loads(q["answer"]) if isinstance(q["answer"], str) else (q["answer"] or {})
        who = SIDES.get(q["raised_by"], "a reader")
        line = f"{q['segment_id']}" + (f", on “{q['span'].strip()}”" if q["span"] else "") + f": {who} raised: {q['reason'].strip()}"
        if q["recommendation"]:
            line += f" Suggested: “{q['recommendation'].strip()}”"
        line += f" Declined: {DECLINED.sub('', answer.get('reason') or '').strip() or 'no reason given.'}"
        rows.append((order[pid], 0, q["id"], line))
    for e in conn.execute("SELECT id, payload FROM event WHERE run_id=? AND type='disagreement.recorded' ORDER BY id", (run_id,)):
        d = json.loads(e["payload"])
        pid = _first_id(d.get("paragraph", ""))
        if pid not in order:
            continue
        line = (f"{d['paragraph']}: the readers disagreed. Against the Japanese: {d.get('faithful_side', '').strip()} "
                f"As English: {d.get('readable_side', '').strip()} Chosen: {d.get('choice', '').strip()}")
        rows.append((order[pid], 1, e["id"], line))
    if not rows:
        return ""
    return context.block(ROAD, "\n".join(f"- {r[-1]}" for r in sorted(rows, key=lambda r: r[:3])))
