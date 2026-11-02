"""Stage 3: crux check. A second Wonder call reads the text without the first reading; a head compares the two cruxes.
"Different" opens the first fork; until the editor rules, Wonder's reading stands."""

from house import context
from house.client import WONDER, Call, load_schema
from house.db import dumps


def cruxes(items: list[dict]) -> str:
    return "\n".join(f"- {c['point']} {c['why']} For the English: {c['for_the_english']}" for c in items)


def run(ctx) -> None:
    src = context.join(context.work_card(ctx.work), context.source_text(ctx.work))
    second = ctx.call("crux-check", Call("crux-check", WONDER, "low", src, load_schema("crux-check"),
                                         f"{ctx.work_id}:source")).data
    reading = ctx.latest("reading")
    options = context.block("What the choice is for", "Two readers read the whole text independently and named its crux. "
                                                      "Do they name the same thing in different words, or different things?")
    options += context.block("Option 0, from the first read (Wonder)", cruxes(reading["crux"]))
    options += context.block("Option 1, from the crux check (Wonder), which never saw option 0", cruxes(second["crux"]))
    head = ctx.call("head", Call("head-select", WONDER, "low", options,
                                 load_schema("head-select"), f"{ctx.work_id}:source")).data
    same = head["same_or_different"] == "same"
    eid = ctx.emit("crux-check", "crux.checked", {"same": same, "second": second, "head": head})
    ctx.save("crux-check", {"second": second, "head": head}, eid)
    opened = ctx.conn.execute("SELECT 1 FROM fork WHERE run_id=? AND anchor='work'", (ctx.run_id,)).fetchone()
    if not same and not opened:
        # Each side's case is its own words, verbatim; the head adds only the one-line trade-offs.
        tradeoffs = [o.get("tradeoff", "") for o in head["fork"].get("options", [])] + ["", ""]
        options = [
            {"author": "first-read (Wonder)", "tradeoff": tradeoffs[0], "case": cruxes(reading["crux"])},
            {"author": "crux-check (Wonder)", "tradeoff": tradeoffs[1], "case": cruxes(second["crux"])},
        ]
        question = head["fork"].get("question") or "What does a translation of this text stand or fall on?"
        pick = 0  # Wonder's reading stands until the editor rules (docs/STORY-STATE.md §0)
        cur = ctx.conn.execute(
            "INSERT INTO fork (run_id, work_id, anchor, question, options, head_pick, head_reason, status) VALUES (?,?,?,?,?,?,?,?)",
            (ctx.run_id, ctx.work_id, "work", question, dumps(options), pick, head["reason"], "open"))
        ctx.conn.commit()
        ctx.emit("head", "fork.opened", {"fork_id": cur.lastrowid, "anchor": "work", "kind": "crux",
                                         "question": question, "head_pick": pick, "reason": head["reason"],
                                         "options": options})
