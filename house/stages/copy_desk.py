"""The copy desk: consistency, after the final read. Three steps.

1. Code makes the choices that need no judgement (checks.style.house_style): straight quotes, one
   dash, British spelling, a silence printed one way.
2. The copy editor, one Spark call with the edit tool the desk and the final read share, makes names,
   terms and italics consistent. It works from two lists code makes: the words the English spells more
   than one way, and the name readings the ruby gives (the first reading once wrote いきなわ as "Ikina",
   and every page followed it: experiment 10). It sees the whole English when the text is short enough
   to send whole; on a book it works from the lists and a find tool that shows where words appear,
   and its edits still reach the whole text.
3. Code checks, which become queries: stray scripts, and paragraphs far shorter than their Japanese.

The model is a run option, options['copy_model'] (stages.common.DEFAULTS).
"""

import json

from house import checks, context, queries
from house.checks import style
from house.client import Call, load_schema
from house.stages.common import FIND_TOOL, Editor, change_flags, edit_tool, label, latest_units, model, new_revision

ACTOR = "copy-desk"
CODE = "copy-desk/code"
MAX_TURNS = 30  # a 15,000-character text took 12 turns for its names alone
WHOLE_ENGLISH_CHARS = 200_000  # about 50,000 tokens: Spark's input is cheap, and cached after the first turn


def house_rules(ctx) -> int:
    ja = {p.id: p.text for p in ctx.work.translatable()}
    changed = 0
    for unit, en in latest_units(ctx).items():
        new = style.house_style(en, "".join(ja.get(i, "") for i in unit))
        if new != en:
            new_revision(ctx, unit, new, {"copy-desk": "house style: quotation marks, dashes, spelling"}, CODE)
            changed += 1
    return changed


def copy_edit(ctx, stats: dict) -> None:
    units = latest_units(ctx)
    bible = ctx.latest("bible")
    found = style.variants(units, label)
    names = style.readings(ctx.work.translatable(), bible, units)
    english = "\n\n".join(f"{label(u)}　{en}" for u, en in units.items())
    whole = context.block("The English", english) if len(english) <= WHOLE_ENGLISH_CHARS else ""
    inp = context.join(context.bible(bible),
                       context.block("Names the English may have misread, against the reading the ruby gives", "\n".join(names) or "None."),
                       context.block("Words the English spells more than one way", "\n".join(found) or "None."), whole)
    editor = Editor(ctx, units)
    res = ctx.loop(ACTOR, Call("copy-desk", model(ctx, "copy_model"), "low", inp, load_schema("copy-desk"),
                               f"{ctx.cache_key()}:copy-desk", expected_output_tokens=3000, tools=[edit_tool(), FIND_TOOL]), editor, max_turns=MAX_TURNS)
    stats["refused"] = editor.refused
    for unit, cur in editor.edited().items():
        rid = new_revision(ctx, unit, cur["english"], {"copy-desk": " ".join(e["reason"] for e in cur["applied"])}, ACTOR)
        for flag in change_flags(units[unit], cur["english"]):
            ctx.emit("copy-desk/code", "check.flagged", {"segment_id": unit[0], "check": flag, "revision_id": rid})
        stats["edited"] += 1
    ctx.emit(ACTOR, "copy.done", {"edited": stats["edited"], "variants": len(found), "readings": len(names),
                                  "summary": res.data["summary"]}, call_id=res.call_id)


def code_checks(ctx) -> int:
    raised = 0
    already = {(r["segment_id"], r["reason"]) for r in ctx.conn.execute(
        "SELECT segment_id, reason FROM query WHERE run_id=? AND raised_by=?", (ctx.run_id, CODE))}
    # One pair per unit: a group the drafter joined is measured as a whole, Japanese against English,
    # and any query lands on its first paragraph.
    ja = {p.id: p.text for p in ctx.work.translatable()}
    pairs = {ids[0]: ("".join(ja.get(i, "") for i in ids), en) for ids, en in latest_units(ctx).items() if ids[0] in ja}
    found = {pid: [("omission", why)] for pid, why in checks.omissions(pairs).items()}
    for pid, (_, en) in pairs.items():
        found.setdefault(pid, [])
        found[pid] += [("other", w) for w in checks.stray_scripts(en)]
    for pid, items in found.items():
        for category, why in items:
            if (pid, why) in already:
                continue
            queries.raise_query(ctx, pid, CODE, {"category": category, "reason": why, "span": None,
                                                 "confidence": "high", "say": f"Copy desk: {why}."})
            raised += 1
    return raised


def run(ctx) -> dict:
    stats = {"house_style": 0, "edited": 0, "refused": 0}
    done = ctx.conn.execute("SELECT 1 FROM event WHERE run_id=? AND type='copy.done'", (ctx.run_id,)).fetchone()
    if not done:
        stats["house_style"] = house_rules(ctx)
        copy_edit(ctx, stats)
    stats["queries"] = code_checks(ctx)
    stats["model"] = model(ctx, "copy_model")
    return stats
