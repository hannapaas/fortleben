"""What several stages share: the ledger as code reads it, the cached prefix for a call about a
page, the current English, and which model an option names."""

import json
import re

from house import context
from house.client import SPARK, WONDER

MODELS = {"spark": SPARK, "wonder": WONDER}


def model(ctx, option: str, default: str = "spark") -> str:
    """The model a run option names: 'spark' or 'wonder' (draft_model, reader_model, desk_model)."""
    name = ctx.options.get(option) or default
    if name not in MODELS:
        raise ValueError(f"{option} must be one of {', '.join(MODELS)}, not {name!r}")
    return MODELS[name]


def terms(ctx) -> dict:
    return {r["id"]: dict(r) for r in ctx.conn.execute("SELECT * FROM term WHERE work_id=?", (ctx.work_id,))}


def stable(ctx, around=None) -> str:
    """The cached prefix for a call about a page: the reading, the bible, and as much of the source
    as the length of the work allows (context.source_text)."""
    bible = ctx.latest("bible")
    return context.join(context.reading(ctx.latest("reading")), context.bible(bible),
                        context.source_text(ctx.work, around, bible.get("chapter_summaries")))


def latest_units(ctx) -> dict[tuple, str]:
    """The current English per unit: a paragraph, or a group the drafter joined, keyed by its ids."""
    units = {}
    for r in ctx.conn.execute("SELECT segment_ids, english FROM revision WHERE run_id=? AND variant='lead' ORDER BY id",
                              (ctx.run_id,)):
        ids = tuple(json.loads(r["segment_ids"]))
        for k in [k for k in units if set(k) & set(ids) and k != ids]:
            del units[k]  # a later unit over the same paragraphs replaces an earlier one
        units[ids] = r["english"]
    return units


def unit_of(units: dict[tuple, str], label: str) -> tuple | None:
    """The unit a model named: 'p12', or a group written 'p21-p23', 'p21–p23' or 'p21, p22, p23'."""
    for ids in units:
        names = {ids[0], "–".join((ids[0], ids[-1])), "-".join((ids[0], ids[-1])), ", ".join(ids), ",".join(ids)}
        if label.strip() in names:
            return ids
    found = next((ids for ids in units if label.strip() in ids), None)
    if found is None:  # a model that wrote "change to p4: ..." still named p4; take the first ID it gives
        m = re.search(r"\bp\d+(?:\s*[-–]\s*p\d+)?", label)
        if m and m.group(0) != label.strip():
            return unit_of(units, re.sub(r"\s*([-–])\s*", r"\1", m.group(0)))
    return found


def latest_english(ctx, variant: str = "lead") -> dict[str, str]:
    rows = ctx.conn.execute(
        "SELECT segment_ids, english FROM revision WHERE run_id=? AND variant=? ORDER BY id", (ctx.run_id, variant)).fetchall()
    out = {}
    for r in rows:
        ids = json.loads(r["segment_ids"])
        for i in ids:
            out[i] = r["english"] if len(ids) == 1 else f"[grouped with {', '.join(ids)}] {r['english']}"
    return out
