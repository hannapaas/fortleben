"""What several stages share: the cached prefix for a call about a page, the current English, and which model an option names."""

import json
import re

from house import context
from house.db import dumps
from house.client import SPARK, WONDER

MODELS = {"spark": SPARK, "wonder": WONDER}
# What a run uses unless told otherwise: the best set-up the experiments found (docs/experiments/).
# Wonder sometimes returned filler for the final read, so it runs on Spark.
DEFAULTS = {"draft_model": "spark", "draft_prompt": "translate-draft-plain", "reader_model": "spark",
            "desk_model": "wonder", "final_model": "spark"}


def model(ctx, option: str) -> str:
    """The model a run option names, 'spark' or 'wonder', or the default for it."""
    name = ctx.options.get(option) or DEFAULTS[option]
    if name not in MODELS:
        raise ValueError(f"{option} must be one of {', '.join(MODELS)}, not {name!r}")
    return MODELS[name]


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
    whole = re.fullmatch(r"(p\d+)\s*[-–,]\s*p\d+.*", label.strip())
    if found is None and whole:  # a range the drafter didn't group: its first paragraph
        return next((ids for ids in units if whole.group(1) in ids), None)
    if found is None:  # a model that wrote "change to p4: ..." still named p4; take the first ID it gives
        m = re.search(r"\bp\d+(?:\s*[-–]\s*p\d+)?", label)
        if m and m.group(0) != label.strip():
            return unit_of(units, re.sub(r"\s*([-–])\s*", r"\1", m.group(0)))
    return found


def latest_english(ctx) -> dict[str, str]:
    """The current English per paragraph, from latest_units; a paragraph in a group the drafter joined
    carries the group's English, marked as such."""
    out = {}
    for ids, en in latest_units(ctx).items():
        for i in ids:
            out[i] = en if len(ids) == 1 else f"[grouped with {', '.join(ids)}] {en}"
    return out


def translator_notes(ctx, pid: str) -> list[str]:
    """The translator's notes on a paragraph's draft (later revisions carry none)."""
    row = ctx.conn.execute("SELECT notes FROM revision WHERE run_id=? AND variant='lead' AND segment_ids LIKE ? "
                           "AND notes IS NOT NULL ORDER BY id DESC LIMIT 1", (ctx.run_id, f'%"{pid}"%')).fetchone()
    return json.loads(row["notes"]) if row else []


def apply_edit(text: str, find: str, replace: str) -> str | None:
    """One exact find-and-replace, as an editor's tool does it: the words must appear once. A quoted
    span copied with its quotation marks, or with stray spaces, is matched without them."""
    for f, r in ((find, replace), (find.strip(), replace.strip()), (find.strip().strip("“”\"‘’'"), replace.strip().strip("“”\"‘’'"))):
        if f and text.count(f) == 1:
            return text.replace(f, r)
    return None


def locked_lines(ctx) -> set[str]:
    return {r["segment_id"] for r in ctx.conn.execute("SELECT segment_id FROM lock WHERE work_id=?", (ctx.work_id,))}


def apply_edits(ctx, units: dict, edits: list[dict], ids: set[str], who: str) -> tuple[dict, int]:
    """Apply exact find-and-replace edits (each with 'paragraph', 'find', 'replace') to the current
    English, as an editor's tool does: an edit outside `ids`, on a locked line, or whose words aren't in
    the paragraph exactly once is refused and flagged, so nothing that wasn't named can change.
    Returns {unit: {"english", "applied": [the edits that went in]}} and the edits that were refused."""
    locked, edited, refused = locked_lines(ctx), {}, []
    for e in edits:
        unit = unit_of(units, e["paragraph"])
        if unit is None or unit[0] not in ids or set(unit) & locked:
            why = "a locked line" if unit and set(unit) & locked else f"{e['paragraph']}, outside this part"
            ctx.emit("house", "check.flagged", {"segment_id": unit[0] if unit else e["paragraph"], "check": f"{who} edit to {why}: refused"})
            refused.append(e)
            continue
        cur = edited.setdefault(unit, {"english": units[unit], "applied": []})
        new = apply_edit(cur["english"], e["find"], e["replace"])
        if new is None:
            ctx.emit("house", "check.flagged", {"segment_id": unit[0], "check": f"{who} edit refused: “{e['find'][:60]}” not found once"})
            refused.append(e)
            continue
        cur["english"] = new
        cur["applied"].append(e)
    return {u: c for u, c in edited.items() if c["english"] != units[u]}, refused


def change_flags(old: str, new: str) -> list[str]:
    """What code checks on a changed paragraph: no stray script, and not shrunk (words gone missing)."""
    from house import checks
    flags = checks.stray_scripts(new)
    if len(new) < 0.7 * len(old):
        flags.append(f"paragraph shrank to {len(new) / max(len(old), 1):.0%} of its length")
    return flags


def new_revision(ctx, unit: tuple, english: str, cause: dict, actor: str) -> int:
    v = ctx.conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant='lead'",
                         (ctx.run_id, dumps(list(unit)))).fetchone()[0]
    cur = ctx.conn.execute("INSERT INTO revision (run_id, work_id, segment_ids, version, english) VALUES (?,?,?,?,?)",
                           (ctx.run_id, ctx.work_id, dumps(list(unit)), v, english))
    eid = ctx.emit(actor, "revision.created", {"segment_id": unit[0], "ids": list(unit), "revision_id": cur.lastrowid, "version": v,
                                               "english": english, "cause": cause})
    ctx.conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, cur.lastrowid))
    ctx.conn.commit()
    return cur.lastrowid
