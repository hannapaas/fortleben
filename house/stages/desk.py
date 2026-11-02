"""Stage 8: the desk. One call per part, the only one that writes after the draft, as the translator owns the
wording in a publishing house and everyone else queries. It gets the
chapter in both languages, both readers' notes numbered side by side (F1… faithful, R1… readable)
and the house's reading, and returns only its edits, each an exact span of the current English and its
replacement, with the notes it answers; the notes it declined and why; and where the readers disagreed.

Code does the rest: a chapter with no notes is never sent; every note must come back taken,
declined or in a disagreement, or it's flagged; an edit whose span isn't in the English is refused, so
nothing the desk didn't name can change; a changed paragraph is checked for stray
scripts and shrinking; locked lines are never
changed; disagreements the reading doesn't settle go up as forks, at most five a run.

One decision per note, with no rounds of debate: rounds can talk agents out of a right answer (Wynn et al.
2025) and into simply agreeing (Yao et al. 2025, docs/REFERENCES.md).

The emergency lever, with no human in it: when the desk learns something in one chapter that changes an
earlier one (who a character is, what a word means here), it says so. Later chapters' desks are told,
and once every chapter has been through the desk, each earlier chapter goes back to the desk once with
those findings as its notes. At most five findings a run, one pass back, no loop.

The model is a run option, options['desk_model'] (orchestrator.DEFAULTS).
"""

import json

from house import checks, context, queries
from house.client import Call, load_schema
from house.db import dumps
from house.stages.common import apply_edits, change_flags, latest_units, model, new_revision, translator_notes

ACTOR = "desk"
MAX_FORKS = 5
MAX_FINDINGS = 5  # findings taken back to earlier chapters, per run
LABELS = {"F": "the faithful reader", "R": "the readable reader", "S": "the desk, from a later chapter"}


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
        ja = "; ".join(json.loads(q["evidence"] or "[]"))
        on = f"on {q['segment_id']}: “{q['span']}”" if q["span"] else f"found at {q['segment_id']}"
        out.append(f"{label} ({LABELS[label[0]]}) {on}\n  {q['reason']}"
                   + (f"\n  {'Why' if label[0] == 'S' else 'Japanese'}: {ja}" if ja else "")
                   + (f"\n  Suggested: {q['recommendation']}" if q["recommendation"] else "")
                   + (f"\n  How sure: {q['confidence']}" if q["confidence"] else ""))
    return context.block("The readers' notes", "\n\n".join(out))


def decided(d: dict) -> set[str]:
    """The note labels an answer from the desk takes, declines or records as a disagreement."""
    return ({n for ch in d["changes"] for n in ch["answers"]} | {x["note"] for x in d["declined"]}
            | {n for dis in d["disagreements"] for n in dis["notes"]})


def drafter_notes(ctx, paras) -> str:
    """The translator's notes on the draft, so the desk knows what a line was meant to do. The readers
    don't get them: their first reaction is worth more uncoached."""
    seen, out = set(), []
    for p in paras:
        for n in translator_notes(ctx, p.id):
            if n not in seen:
                seen.add(n)
                out.append(f"{p.id}: {n}")
    return context.block("The translator's notes on the draft", "\n".join(out) or "None.")


def standing(ctx) -> str:
    rules = [r["text"] for r in ctx.conn.execute("SELECT text FROM rule WHERE (work_id=? OR work_id IS NULL) AND status='active'",
                                                  (ctx.work_id,))]
    locks = [r["segment_id"] for r in ctx.conn.execute("SELECT segment_id FROM lock WHERE work_id=?", (ctx.work_id,))]
    return context.block("Standing rules and locked lines",
                         ("Rules: " + "; ".join(rules) if rules else "No standing rules.") + "\n"
                         + ("Locked: " + ", ".join(locks) if locks else "No locked lines."))


def forks_so_far(ctx) -> int:
    return ctx.conn.execute("SELECT COUNT(*) FROM fork WHERE run_id=? AND anchor != 'work'", (ctx.run_id,)).fetchone()[0]


def findings(ctx) -> list[dict]:
    """What the desk has learned so far that reaches beyond its chapter."""
    return [dict(r) for r in ctx.conn.execute(
        "SELECT * FROM query WHERE run_id=? AND owner='desk-recheck' ORDER BY id", (ctx.run_id,))]


def findings_block(found: list[dict]) -> str:
    if not found:
        return ""
    return context.block("What the desk learned in earlier chapters",
                         "\n".join(f"- {q['reason']} Why: {'; '.join(json.loads(q['evidence'] or '[]'))} (found at {q['segment_id']})"
                                   for q in found))


def record_findings(ctx, paras, d: dict, recheck: bool) -> None:
    for f in d["beyond_this_chapter"]:
        if recheck:
            ctx.emit("house", "check.flagged", {"segment_id": paras[0].id,
                                                "check": f"finding on the way back, not taken back again: {f['finding']}"})
        elif len(findings(ctx)) >= MAX_FINDINGS:
            ctx.emit("house", "check.flagged", {"segment_id": paras[0].id, "check": f"findings cap reached, not taken back: {f['finding']}"})
        else:
            queries.raise_query(ctx, paras[0].id, ACTOR, {"category": "beyond-chapter", "reason": f["finding"],
                                                          "evidence_ja": f["why"], "say": f["finding"]}, owner="desk-recheck")


def desk_chapter(ctx, paras, units: dict, stats: dict, notes: dict | None = None) -> None:
    recheck = notes is not None  # a chapter taken back to the desk with findings from later chapters
    notes = notes if recheck else chapter_notes(ctx, paras)
    if not notes:
        ctx.emit(ACTOR, "desk.done", {"ids": [p.id for p in paras], "skipped": True, "reason": "no notes"})
        stats["skipped"] += 1
        return
    inp = context.join(context.reading(ctx.latest("reading")),
                       context.block("The cast", context.cast(ctx.latest("bible"))),
                       standing(ctx), context.chapter_pairs(paras, units, "ja"), drafter_notes(ctx, paras),
                       "" if recheck else findings_block(findings(ctx)), render_notes(notes))
    for attempt in range(2):  # an answer that decides none of the notes is asked for once more
        res = ctx.call(ACTOR, Call("desk", model(ctx, "desk_model"), "medium", inp, load_schema("desk"),
                                   f"{ctx.cache_key()}:desk", expected_output_tokens=7000, strict=True))  # once a chapter
        if decided(res.data) & set(notes) or attempt:
            break
        ctx.emit("house", "check.flagged", {"segment_id": paras[0].id, "check": "the desk decided none of the notes: asked again"})
        inp = context.join(inp, context.block("A note on the previous attempt",
                                              f"The previous answer decided none of the {len(notes)} notes. Each one needs a decision: "
                                              "a change that answers it, or a reason it's declined."))
    d = res.data
    record_findings(ctx, paras, d, recheck)
    ids = {p.id for p in paras}
    accounted = set()
    edited, refused = apply_edits(ctx, units, d["changes"], ids, "desk")
    stats["refused"] += len(refused)
    for ch in refused:  # the desk answered these notes, but its edit didn't match the English
        for n in ch["answers"]:
            if n in notes and n not in accounted:
                queries.set_status(ctx, notes[n]["id"], "unaddressed", "house", {"note": n, "reason": "the desk's edit didn't match the English"})
                accounted.add(n)
                stats["unaddressed"] += 1
    for unit, cur in edited.items():
        cur["answers"] = [n for ch in cur["applied"] for n in ch["answers"] if n in notes]
        cur["reasons"] = [ch["reason"] for ch in cur["applied"]]
        stats["unprompted"] += sum(not ch["answers"] for ch in cur["applied"])
        flags = change_flags(units[unit], cur["english"])
        rid = new_revision(ctx, unit, cur["english"], {"desk": " ".join(cur["reasons"]), "notes": cur["answers"],
                                                      "unprompted": not cur["answers"]}, ACTOR)
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
                queries.set_status(ctx, notes[n]["id"], "forked", ACTOR, {"note": n, "fork_id": cur.lastrowid})

    for n, q in notes.items():
        if n not in accounted and q["status"] == "open":
            queries.set_status(ctx, q["id"], "unaddressed", "house", {"note": n, "reason": "the desk didn't address it"})
            ctx.emit("house", "check.flagged", {"segment_id": q["segment_id"], "check": f"note {n} not addressed by the desk"})
            stats["unaddressed"] += 1
    ctx.emit(ACTOR, "desk.done", {"ids": [p.id for p in paras], "notes": len(notes), "changed": len(edited),
                                  "recheck": recheck}, call_id=res.call_id)


def to_take_back(chapters: list, found: list[dict]) -> list[tuple[int, list[dict]]]:
    """Which earlier chapters go back to the desk, with which findings: each finding goes to every
    chapter before the one it was found in."""
    start = {paras[0].id: i for i, paras in enumerate(chapters)}
    owner = {}
    for i, paras in enumerate(chapters):
        for p in paras:
            owner[p.id] = i
    out = []
    for i in range(len(chapters)):
        later = [q for q in found if owner.get(q["segment_id"], start.get(q["segment_id"], -1)) > i]
        if later:
            out.append((i, later))
    return out


def run(ctx) -> dict:
    events = [json.loads(r["payload"]) for r in ctx.conn.execute(
        "SELECT payload FROM event WHERE run_id=? AND type='desk.done'", (ctx.run_id,))]
    done = {e["ids"][0] for e in events if not e.get("recheck")}
    rechecked = {e["ids"][0] for e in events if e.get("recheck")}
    stats = {k: 0 for k in ("chapters", "skipped", "changed", "unprompted", "taken", "declined", "disagreements",
                            "forks", "unaddressed", "refused", "flags", "findings", "taken_back")}
    chapters = context.chapters(ctx.work)
    for paras in chapters:
        stats["chapters"] += 1
        if paras[0].id not in done:
            desk_chapter(ctx, paras, latest_units(ctx), stats)
    # the lever: earlier chapters go back to the desk, once, with what later chapters taught it
    found = findings(ctx)  # all of them: on a resume, chapters already taken back have changed their status
    stats["findings"] = len(findings(ctx))
    for i, later in to_take_back(chapters, found):
        paras = chapters[i]
        if paras[0].id not in rechecked:
            desk_chapter(ctx, paras, latest_units(ctx), stats, notes={f"S{n + 1}": q for n, q in enumerate(later)})
            stats["taken_back"] += 1
    for q in findings(ctx):  # one found in the first chapter has nowhere earlier to go
        if ctx.conn.execute("SELECT status FROM query WHERE id=?", (q["id"],)).fetchone()["status"] == "open":
            queries.set_status(ctx, q["id"], "noted", "house", {"reason": "no earlier chapter to take it back to"})
    stats["model"] = model(ctx, "desk_model")
    return stats
