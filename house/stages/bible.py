"""Stage 4: bible. The Analyst writes the story bible from the whole source and the reading, in one
call: cast, narration, motifs, style sheet, part summaries (for a book in more than one part), hard spots. No referent map: who speaks and acts
in a given sentence is worked out by whoever reads that sentence, with the text in front of them
(docs/STORY-STATE.md §6)."""

from house import context
from house.client import SPARK, Call, load_schema


def run(ctx) -> dict:
    parts = context.chapters(ctx.work)
    plan = context.block("The parts the house has divided the book into",
                         "\n".join(f"- {p[0].id}–{p[-1].id}" for p in parts)) if len(parts) > 1 else ""
    stable = context.join(context.work_card(ctx.work), context.source_text(ctx.work),
                          context.reading(ctx.latest("reading")), plan)
    res = ctx.call("analyst", Call("analyst-bible", SPARK, "medium", stable, load_schema("analyst-bible"),
                                   f"{ctx.work_id}:analyst", expected_output_tokens=8000))
    bible = res.data
    by_start = {s["starts"]: s["summary"] for s in bible.get("part_summaries", [])}
    bible["chapter_summaries"] = {str(i): by_start[p[0].id] for i, p in enumerate(parts) if p[0].id in by_start}
    eid = ctx.emit("analyst", "bible.written", {"version": ctx.version("bible") + 1, "cast": len(bible["cast"]),
                                                "motifs": len(bible["motifs"])},
                   call_id=res.call_id)
    ctx.save("bible", bible, eid)
    return {"cast": len(bible["cast"]), "motifs": len(bible["motifs"])}
