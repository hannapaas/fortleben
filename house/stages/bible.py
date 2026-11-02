"""Stage 4: bible. The Analyst writes the story bible from the whole source and the reading, in one
call: cast, narration, motifs, style sheet, hard spots. No referent map: who speaks and acts
in a given sentence is worked out by whoever reads that sentence, with the text in front of them
(docs/STORY-STATE.md §6)."""

from house import context
from house.client import SPARK, Call, load_schema


def run(ctx) -> dict:
    stable = context.join(context.work_card(ctx.work), context.source_text(ctx.work),
                          context.reading(ctx.latest("reading")))
    res = ctx.call("analyst", Call("analyst-bible", SPARK, "medium", stable, load_schema("analyst-bible"),
                                   f"{ctx.work_id}:analyst", expected_output_tokens=8000))
    bible = res.data
    eid = ctx.emit("analyst", "bible.written", {"version": ctx.version("bible") + 1, "cast": len(bible["cast"]),
                                                "motifs": len(bible["motifs"])},
                   call_id=res.call_id)
    ctx.save("bible", bible, eid)
    return {"cast": len(bible["cast"]), "motifs": len(bible["motifs"])}
