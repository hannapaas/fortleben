"""Stage 9: final read. Once the desk is done, one reader reads the finished English as a whole, then
against the Japanese, for what only shows across the whole: seams revision left, voice drift,
continuity, a word an edit doubled. Small certain repairs come back as exact edits, applied by code as
the desk's are; anything larger goes to the editor as a note.

A text up to context.WHOLE_TEXT_CHARS is read in one call; a longer one a part at a time, each with
the reading and the bible, so every call still sees what the house knows about the whole.
The model is a run option, options['final_model'] (orchestrator.DEFAULTS).
"""

import json

from house import context, queries
from house.client import Call, load_schema
from house.stages.common import apply_edits, change_flags, latest_units, model, new_revision, unit_of

ACTOR = "final-read"


def parts(work) -> list[list]:
    """What one call reads: the whole text when it fits, otherwise a chapter."""
    paras = work.translatable()
    return context.chapters(work) if context.is_long(work) else [paras]


def read(ctx, paras, units: dict, stats: dict) -> None:
    bible = ctx.latest("bible")
    others = [f"- {p[0].id}–{p[-1].id}: {context.chapter_line(p, bible.get('chapter_summaries'), i)}"
              for i, p in enumerate(context.chapters(ctx.work)) if p[0].id != paras[0].id]
    inp = context.join(context.reading(ctx.latest("reading")), context.bible(bible),
                       context.block("The rest of the book, in brief", "\n".join(others)) if others and len(paras) < len(ctx.work.translatable()) else "",
                       context.chapter_pairs(paras, units, "en"))
    res = ctx.call(ACTOR, Call("final-read", model(ctx, "final_model"), "medium", inp,
                               load_schema("final-read"), f"{ctx.cache_key()}:final-read",
                               expected_output_tokens=5000, strict=True))
    edited, refused = apply_edits(ctx, units, res.data["fixes"], {p.id for p in paras}, "final-read")
    stats["refused"] += len(refused)
    for unit, cur in edited.items():
        stats["fixes"] += len(cur["applied"])
        rid = new_revision(ctx, unit, cur["english"], {"final-read": " ".join(f["reason"] for f in cur["applied"])}, ACTOR)
        for flag in change_flags(units[unit], cur["english"]):
            ctx.emit("final-read/code", "check.flagged", {"segment_id": unit[0], "check": flag, "revision_id": rid})
    for n in res.data["notes"]:
        unit = unit_of(units, n["paragraph"])
        anchor = unit[0] if unit else paras[0].id
        queries.raise_query(ctx, anchor, ACTOR, {"span": n["span"], "category": "final-read", "reason": n["problem"],
                                                 "evidence_ja": n["evidence"], "say": n["problem"]}, owner="editor")
        stats["notes"] += 1
    ctx.emit(ACTOR, "final.read", {"ids": [p.id for p in paras], "fixes": len(res.data["fixes"]),
                                   "notes": len(res.data["notes"]), "verdict": res.data["verdict"]}, call_id=res.call_id)


def run(ctx) -> dict:
    done = {json.loads(r["payload"])["ids"][0] for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='final.read'", (ctx.run_id,))}
    stats = {"calls": 0, "fixes": 0, "notes": 0, "refused": 0}
    for paras in parts(ctx.work):
        if paras[0].id not in done:
            read(ctx, paras, latest_units(ctx), stats)
            stats["calls"] += 1
    stats["model"] = model(ctx, "final_model")
    return stats
