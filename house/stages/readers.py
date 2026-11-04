"""Stage 7: readers. Two readers read each chapter independently, and never see each other or the
translator's notes. The faithful reader holds the author's side and meets the Japanese first; the
readable reader holds the English reader's side and meets the English first. Each returns margin
notes or none (at most twenty a chapter, by schema). Notes are stored as queries owned by the desk.

Separate readers, not the translator revising itself: a model judging its own draft favours it (Xu et al.
2024, docs/REFERENCES.md). The model is a run option, options['reader_model'] (stages.common.DEFAULTS).
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


def read(ctx, reader: str, paras, units: dict):
    """One reader's call on one chapter. It stores nothing, so the readers can read side by side."""
    spec = READERS[reader]
    bible = ctx.latest("bible")
    inp = context.join(
        context.reading(ctx.latest("reading")),
        context.bible(bible),
        context.chapter_pairs(paras, units, spec["first"]),
    )
    return ctx.call(actor(reader), Call(spec["prompt"], model(ctx, "reader_model"), "medium", inp,
                                        load_schema(spec["prompt"]), f"{ctx.cache_key()}:{spec['prompt']}",
                                        expected_output_tokens=5000, strict=True))  # once a chapter: strict costs little


def file_notes(ctx, reader: str, paras, units: dict, res) -> int:
    """A reader's notes on a chapter, stored as queries for the desk."""
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
    chapters = context.chapters(ctx.work)
    todo = [(reader, paras) for paras in chapters for reader in READERS if (reader, paras[0].id) not in done]
    stats = {"chapters": len(chapters), "faithful": 0, "readable": 0}

    def store(t, res):  # filed in the order they were read one by one
        stats[t[0]] += file_notes(ctx, t[0], t[1], units, res)

    ctx.side_by_side(lambda c, t: read(c, t[0], t[1], units), todo, then=store)  # every reader is independent
    stats["model"] = model(ctx, "reader_model")
    return stats
