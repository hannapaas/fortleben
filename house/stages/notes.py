"""Stage 13: notes, one call per page. The keikaku test: only what the sentence can't give you.
Notes start unverified; fact-check (stage 14) verifies or kills them."""

import json

from house import context, pager
from house.client import SPARK, Call, load_schema
from house.db import dumps
from house.stages import source_check
from house.stages.draft import latest_english

ACTOR = "notes"


def translator_notes(ctx, pid: str) -> list[str]:
    row = ctx.conn.execute("SELECT notes FROM revision WHERE run_id=? AND variant='lead' AND segment_ids LIKE ? "
                           "AND notes IS NOT NULL ORDER BY id DESC LIMIT 1", (ctx.run_id, f'%"{pid}"%')).fetchone()
    return json.loads(row["notes"]) if row else []


def run(ctx) -> dict:
    english = latest_english(ctx)
    done = {json.loads(r["payload"]).get("page") for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='note.written'", (ctx.run_id,))}
    written = 0
    for paras in pager.pages(ctx.work.paragraphs):
        if paras[0].id in done:
            continue
        body = "\n\n".join(
            f"{p.id}　{p.model_text.strip('　 ')}\n{p.id}　{english.get(p.id, '')}"
            + "".join(f"\n  translator's note: {n}" for n in translator_notes(ctx, p.id)) for p in paras)
        inp = context.join(source_check.stable(ctx), context.block("The page, Japanese and English", body))
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
            eid = ctx.emit(ACTOR, "note.written", {"note_id": cur.lastrowid, "page": paras[0].id, **n},
                           call_id=res.call_id)
            ctx.conn.execute("UPDATE note SET event_id=? WHERE id=?", (eid, cur.lastrowid))
            written += 1
        if not res.data["notes"]:  # mark the page done even when it needs no notes
            ctx.emit(ACTOR, "note.written", {"page": paras[0].id, "none": True}, call_id=res.call_id)
        ctx.conn.commit()
    return {"notes": written}
