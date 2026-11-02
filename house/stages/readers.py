"""Stage 7: readers. Two readers read each chapter independently, and never see each other or the
translator's notes. The faithful reader holds the author's side and meets the Japanese first; the
readable reader holds the English reader's side and meets the English first. Each returns margin
notes or none (at most twenty a chapter, by schema). Notes are stored as queries owned by the desk.

The model is a run option, options['reader_model'] = 'spark' (default) or 'wonder'.
"""

import json

from house import context, queries
from house.client import Call, load_schema
from house.stages.common import latest_units, model, unit_of

READERS = {
    "faithful": {"prompt": "reader-faithful", "first": "ja"},
    "readable": {"prompt": "reader-readable", "first": "en"},
}


def actor(reader: str) -> str:
    return f"reader/{reader}"


def read_chapter(ctx, reader: str, paras, units: dict) -> int:
    spec = READERS[reader]
    bible = ctx.latest("bible")
    inp = context.join(
        context.reading(ctx.latest("reading")),
        context.block("The cast", context.cast(bible)),
        context.chapter_pairs(paras, units, spec["first"]),
    )
    res = ctx.call(actor(reader), Call(spec["prompt"], model(ctx, "reader_model"), "medium", inp,
                                       load_schema(spec["prompt"]), f"{ctx.cache_key()}:{spec['prompt']}",
                                       expected_output_tokens=5000, strict=True))  # once a chapter: strict costs little
    ids = {p.id for p in paras}
    n = 0
    for note in res.data["notes"]:
        unit = unit_of(units, note["paragraph"])
        if unit is None or unit[0] not in ids:
            ctx.emit("house", "check.flagged", {"check": "note anchored outside the chapter", "reader": reader,
                                                "segment_id": note["paragraph"]})
            continue
        found = note["span"] in units[unit]
        queries.raise_query(ctx, unit[0], actor(reader), {
            "span": note["span"], "category": reader, "reason": note["problem"],
            "evidence_ja": note["japanese"], "suggested_fix": note["suggestion"], "confidence": note["sureness"],
            "say": note["problem"] if found else f"{note['problem']} (span not found verbatim in the English)",
        }, owner="desk")
        n += 1
    ctx.emit(actor(reader), "chapter.read", {"ids": [p.id for p in paras], "reader": reader, "notes": n},
             call_id=res.call_id)
    return n


def run(ctx) -> dict:
    units = latest_units(ctx)
    done = {(json.loads(r["payload"])["reader"], json.loads(r["payload"])["ids"][0]) for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='chapter.read'", (ctx.run_id,))}
    stats = {"chapters": 0, "faithful": 0, "readable": 0}
    for paras in context.chapters(ctx.work):
        stats["chapters"] += 1
        for reader in READERS:
            if (reader, paras[0].id) not in done:
                stats[reader] += read_chapter(ctx, reader, paras, units)
    stats["model"] = model(ctx, "reader_model")
    return stats
