"""Stage 13: notes, one call per chapter, on the finished English. The keikaku test: only what the sentence can't give you.
Notes start unverified; fact-check (stage 14) verifies or kills them."""

import json

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
        inp = context.join(stable(ctx, paras), context.block("The chapter, Japanese and English", body))
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
