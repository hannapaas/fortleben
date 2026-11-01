"""Stage 4: bible. The Analyst writes the story bible from the whole source and the reading,
then the referent map and tiers, one call per ~5 pages, each still seeing the whole text."""

from house import context, pager
from house.client import SPARK, Call, load_schema
from house.db import dumps

PAGES_PER_CALL = 5


def ranges(work, per_call: int = PAGES_PER_CALL) -> list[list]:
    pages = pager.pages(work.paragraphs)
    return [sum(pages[i:i + per_call], []) for i in range(0, len(pages), per_call)]


def paragraph_range(paras) -> str:
    body = "\n\n".join(p.id + "\n" + "\n".join(f"  {s['id']}  {s['text']}" for s in p.sentences) for p in paras)
    return context.block(f"The paragraphs to map: {paras[0].id}–{paras[-1].id}, sentence by sentence", body)


def run(ctx) -> dict:
    src = context.source_text(ctx.work)
    reading = context.reading(ctx.latest("reading"))
    stable = context.join(context.work_card(ctx.work), src, reading)

    res = ctx.call("analyst", Call("analyst-bible", SPARK, "medium", stable, load_schema("analyst-bible"),
                                   f"{ctx.work_id}:analyst", expected_output_tokens=8000))
    bible = res.data
    eid = ctx.emit("analyst", "bible.written", {"version": ctx.version("bible") + 1, "cast": len(bible["cast"]),
                                                "ledger": len(bible["ledger"]), "motifs": len(bible["motifs"])},
                   call_id=res.call_id)
    ctx.save("bible", bible, eid)
    for t in bible["ledger"]:
        ctx.conn.execute(
            """INSERT INTO term (id, work_id, source, reading, casual, curious, student, rationale) VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(work_id, id) DO UPDATE SET source=excluded.source, casual=excluded.casual,
               curious=excluded.curious, student=excluded.student, rationale=excluded.rationale""",
            (t["id"], ctx.work_id, t["source"], t.get("reading"), t["casual"], t["curious"], t["student"], t["rationale"]))
    ctx.conn.commit()

    # the referent map, a few pages per call, the whole text and the bible in the stable prefix
    with_bible = context.join(stable, context.bible(bible))
    refmap, amendments = {}, []
    for paras in ranges(ctx.work):
        res = ctx.call("analyst", Call("analyst-referents", SPARK, "low", context.join(with_bible, paragraph_range(paras)),
                                       load_schema("analyst-referents"), f"{ctx.work_id}:analyst-referents",
                                       expected_output_tokens=6000))
        wanted = {p.id for p in paras}
        got = {p["id"]: p for p in res.data["paragraphs"] if p["id"] in wanted}
        missing = sorted(wanted - set(got), key=lambda x: int(x[1:]))
        refmap.update(got)
        amendments += res.data["amendments"]
        ctx.emit("analyst", "referents.written", {"range": [paras[0].id, paras[-1].id], "paragraphs": len(got),
                                                  "missing": missing, "amendments": res.data["amendments"]},
                 call_id=res.call_id)
    for pid, entry in refmap.items():
        ctx.conn.execute("UPDATE segment SET tier=?, tier_reason=? WHERE work_id=? AND id=?",
                         (entry["tier"], entry["tier_reason"], ctx.work_id, pid))
    ctx.conn.commit()
    ctx.save("referents", {"paragraphs": refmap, "amendments": amendments})
    tiers = {}
    for e in refmap.values():
        tiers[e["tier"]] = tiers.get(e["tier"], 0) + 1
    return {"cast": len(bible["cast"]), "ledger": len(bible["ledger"]), "tiers": tiers,
            "referent_entries": sum(len(e["entries"]) for e in refmap.values()), "amendments": len(amendments)}
