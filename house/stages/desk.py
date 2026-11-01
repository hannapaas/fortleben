"""Stage 8: the desk. One call per chapter, the only one that writes after the draft. It gets the
chapter in both languages, both readers' notes numbered side by side (F1… faithful, R1… readable)
and the house's reading, and returns only its edits, each an exact span of the current English and its
replacement, with the notes it answers; the notes it declined and why; and where the readers disagreed.

Code does the rest: a chapter with no notes is never sent; every note must come back taken,
declined or in a disagreement, or it's flagged; an edit whose span isn't in the English is refused, so
nothing the desk didn't name can change; a changed paragraph is checked for dropped ledger
tokens, stray scripts, shrinking and a change far larger than its notes; locked lines are never
changed; disagreements the reading doesn't settle go up as forks, at most five a run.

The model is a run option, options['desk_model'] = 'spark' (default) or 'wonder'.
"""

import difflib
import json

from house import checks, context, queries
from house.client import Call, load_schema
from house.db import dumps
from house.stages.common import latest_units, model, terms, unit_of

ACTOR = "desk"
MAX_FORKS = 5


def chapter_notes(ctx, paras) -> dict[str, dict]:
    """The open notes on this chapter, numbered in the order the readers left them."""
    ids = {p.id for p in paras}
    labelled, counts = {}, {"faithful": 0, "readable": 0}
    for q in queries.open_queries(ctx):
        if q["owner"] != "desk" or q["segment_id"] not in ids:
            continue
        counts[q["category"]] += 1
        labelled[f"{'F' if q['category'] == 'faithful' else 'R'}{counts[q['category']]}"] = q
    return labelled


def render_notes(notes: dict[str, dict]) -> str:
    out = []
    for label, q in notes.items():
        reader = "the faithful reader" if label.startswith("F") else "the readable reader"
        ja = "; ".join(json.loads(q["evidence"] or "[]"))
        out.append(f"{label} ({reader}) on {q['segment_id']}: “{q['span']}”\n  {q['reason']}"
                   + (f"\n  Japanese: {ja}" if ja else "")
                   + (f"\n  Suggested: {q['recommendation']}" if q["recommendation"] else "")
                   + f"\n  How sure: {q['confidence']}")
    return context.block("The readers' notes", "\n\n".join(out))


def standing(ctx) -> str:
    rules = [r["text"] for r in ctx.conn.execute("SELECT text FROM rule WHERE (work_id=? OR work_id IS NULL) AND status='active'",
                                                  (ctx.work_id,))]
    locks = [r["segment_id"] for r in ctx.conn.execute("SELECT segment_id FROM lock WHERE work_id=?", (ctx.work_id,))]
    return context.block("Standing rules and locked lines",
                         ("Rules: " + "; ".join(rules) if rules else "No standing rules.") + "\n"
                         + ("Locked: " + ", ".join(locks) if locks else "No locked lines."))


def change_flags(old: str, new: str, answered: list[dict], t: dict) -> list[str]:
    flags = []
    lost = set(checks.TOKEN.findall(old)) - set(checks.TOKEN.findall(new))
    flags += [f"ledger token {{t:{x}}} dropped" for x in sorted(lost)]
    flags += checks.ledger(new, t) + checks.stray_scripts(new)
    if len(new) < 0.7 * len(old):
        flags.append(f"paragraph shrank to {len(new) / max(len(old), 1):.0%} of its length")
    sm = difflib.SequenceMatcher(None, old, new)
    changed = len(old) + len(new) - 2 * sum(b.size for b in sm.get_matching_blocks())
    allowance = 2 * sum(len(q["span"] or "") for q in answered) + 60
    if changed > allowance and sm.ratio() < 0.8:
        flags.append(f"change of {changed} characters is far larger than the notes it answers")
    return flags


def new_revision(ctx, unit: tuple, english: str, cause: dict) -> int:
    v = ctx.conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant='lead'",
                         (ctx.run_id, dumps(list(unit)))).fetchone()[0]
    cur = ctx.conn.execute("INSERT INTO revision (run_id, work_id, segment_ids, version, english) VALUES (?,?,?,?,?)",
                           (ctx.run_id, ctx.work_id, dumps(list(unit)), v, english))
    eid = ctx.emit(ACTOR, "revision.created", {"segment_id": unit[0], "ids": list(unit), "revision_id": cur.lastrowid, "version": v,
                                               "english": english, "cause": cause})
    ctx.conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, cur.lastrowid))
    ctx.conn.commit()
    return cur.lastrowid


def forks_so_far(ctx) -> int:
    return ctx.conn.execute("SELECT COUNT(*) FROM fork WHERE run_id=? AND anchor != 'work'", (ctx.run_id,)).fetchone()[0]


def desk_chapter(ctx, paras, units: dict, stats: dict) -> None:
    notes = chapter_notes(ctx, paras)
    if not notes:
        ctx.emit(ACTOR, "desk.done", {"ids": [p.id for p in paras], "skipped": True, "reason": "no notes"})
        stats["skipped"] += 1
        return
    inp = context.join(context.reading(ctx.latest("reading")),
                       context.block("The cast and ledger", context.cast_and_ledger(ctx.latest("bible"))),
                       standing(ctx), context.chapter_pairs(paras, units, "ja"), render_notes(notes))
    res = ctx.call(ACTOR, Call("desk", model(ctx, "desk_model"), "medium", inp, load_schema("desk"),
                               f"{ctx.cache_key()}:desk", expected_output_tokens=4000, strict=True))  # once a chapter
    d = res.data
    ids = {p.id for p in paras}
    locked = {r["segment_id"] for r in ctx.conn.execute("SELECT segment_id FROM lock WHERE work_id=?", (ctx.work_id,))}
    t = terms(ctx)
    accounted = set()

    # Apply the edits: each replaces an exact span of the current English. An edit whose span isn't
    # there is refused, so nothing the desk didn't name can change or go missing.
    edited: dict[tuple, dict] = {}  # unit -> {"english", "answers", "reasons"}
    for ch in d["changes"]:
        unit = unit_of(units, ch["paragraph"])
        if unit is None or unit[0] not in ids or set(unit) & locked:
            why = "locked line: change refused" if unit and set(unit) & locked else f"change to {ch['paragraph']}, not in this chapter: refused"
            ctx.emit("house", "check.flagged", {"segment_id": unit[0] if unit else ch["paragraph"], "check": why})
            stats["refused"] += 1
            continue
        cur = edited.setdefault(unit, {"english": units[unit], "answers": [], "reasons": []})
        if not ch["find"] or cur["english"].count(ch["find"]) != 1:
            why = "not found" if ch["find"] not in cur["english"] else "found more than once"
            ctx.emit("house", "check.flagged", {"segment_id": unit[0], "check": f"desk edit refused: “{ch['find'][:60]}” {why}"})
            stats["refused"] += 1
            continue
        cur["english"] = cur["english"].replace(ch["find"], ch["replace"])
        cur["answers"] += [n for n in ch["answers"] if n in notes]
        cur["reasons"].append(ch["reason"])
        stats["unprompted"] += int(not ch["answers"])

    for unit, cur in edited.items():
        if cur["english"] == units[unit]:
            continue
        answered = [notes[n] for n in cur["answers"]]
        flags = change_flags(units[unit], cur["english"], answered, t)
        rid = new_revision(ctx, unit, cur["english"], {"desk": " ".join(cur["reasons"]), "notes": cur["answers"],
                                                      "unprompted": not cur["answers"]})
        for f in flags:
            ctx.emit("desk/code", "check.flagged", {"segment_id": unit[0], "check": f, "revision_id": rid})
        stats["flags"] += len(flags)
        stats["changed"] += 1
        for n in cur["answers"]:
            if n not in accounted:
                queries.set_status(ctx, notes[n]["id"], "taken", ACTOR,
                                   {"note": n, "reason": " ".join(cur["reasons"]), "revision_id": rid})
                accounted.add(n)
                stats["taken"] += 1

    for dec in d["declined"]:
        n = dec["note"]
        if n in notes and n not in accounted:
            queries.set_status(ctx, notes[n]["id"], "declined", ACTOR, {"note": n, "reason": dec["reason"]})
            accounted.add(n)
            stats["declined"] += 1

    for dis in d["disagreements"]:
        record = {k: dis[k] for k in ("notes", "paragraph", "faithful_side", "readable_side", "choice", "send_up")}
        ctx.emit(ACTOR, "disagreement.recorded", record, call_id=res.call_id)
        stats["disagreements"] += 1
        if not dis["send_up"]:
            continue
        if forks_so_far(ctx) >= MAX_FORKS:
            ctx.emit("house", "check.flagged", {"segment_id": dis["paragraph"], "check": "fork cap reached: recorded, not sent up"})
            continue
        options = [{"author": "reader/faithful", "case": dis["faithful_side"]},
                   {"author": "reader/readable", "case": dis["readable_side"]}]
        cur = ctx.conn.execute(
            "INSERT INTO fork (run_id, work_id, anchor, question, options, head_reason, status) VALUES (?,?,?,?,?,?,?)",
            (ctx.run_id, ctx.work_id, dis["paragraph"], f"The readers disagree at {dis['paragraph']}", dumps(options),
             dis["choice"], "open"))
        ctx.conn.commit()
        ctx.emit(ACTOR, "fork.opened", {"fork_id": cur.lastrowid, "anchor": dis["paragraph"], "kind": "readers",
                                        "notes": dis["notes"], "options": options, "desk_choice": dis["choice"]})
        stats["forks"] += 1
        for n in dis["notes"]:
            if n in notes:
                accounted.add(n)
                ctx.conn.execute("UPDATE query SET status='forked' WHERE id=?", (notes[n]["id"],))
        ctx.conn.commit()

    for n, q in notes.items():
        if n not in accounted and q["status"] == "open":
            still_open = ctx.conn.execute("SELECT status FROM query WHERE id=?", (q["id"],)).fetchone()["status"] == "open"
            if still_open:
                queries.set_status(ctx, q["id"], "unaddressed", "house", {"note": n, "reason": "the desk didn't address it"})
                ctx.emit("house", "check.flagged", {"segment_id": q["segment_id"], "check": f"note {n} not addressed by the desk"})
                stats["unaddressed"] += 1
    ctx.emit(ACTOR, "desk.done", {"ids": [p.id for p in paras], "notes": len(notes), "changed": len(edited)},
             call_id=res.call_id)


def run(ctx) -> dict:
    done = {json.loads(r["payload"])["ids"][0] for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='desk.done'", (ctx.run_id,))}
    stats = {k: 0 for k in ("chapters", "skipped", "changed", "unprompted", "taken", "declined", "disagreements",
                            "forks", "unaddressed", "refused", "flags")}
    for paras in context.chapters(ctx.work):
        stats["chapters"] += 1
        if paras[0].id not in done:
            desk_chapter(ctx, paras, latest_units(ctx), stats)
    stats["model"] = model(ctx, "desk_model")
    return stats
