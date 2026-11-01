"""Stage 9: answer. For each paragraph with open queries, Translation answers them all in one
call: accepted, stet or revised. Only a contested answer (stet or revised) goes back to the
critic that raised it, with the diff; the critic closes or raises again. An accepted query is
closed by code once the English has actually changed; if the translator accepted and the text
didn't move, the critic re-checks after all. Code enforces the limits (docs/STAGES.md): two
rounds per query, then a fork on a hard paragraph or the translator's text stands as the head's
pick, labelled; three revision cycles per paragraph, then flagged unresolved."""

import json

from house import context, queries
from house.client import SPARK, WONDER, Call, load_schema
from house.db import dumps
from house.stages import source_check
from house.stages.draft import latest_english

ACTOR = "translation/answer"
MAX_REVISIONS = 3


def tier(ctx, pid: str) -> str:
    row = ctx.conn.execute("SELECT tier FROM segment WHERE work_id=? AND id=?", (ctx.work_id, pid)).fetchone()
    return (row["tier"] if row else None) or "plain"


def revisions_by_answer(ctx, pid: str) -> int:
    return ctx.conn.execute("SELECT COUNT(*) FROM revision WHERE run_id=? AND variant='lead' AND segment_ids=? AND version > 1",
                            (ctx.run_id, dumps([pid]))).fetchone()[0]


def new_revision(ctx, pid: str, english: str, cause: list[int]) -> int:
    v = ctx.conn.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM revision WHERE run_id=? AND segment_ids=? AND variant='lead'",
                         (ctx.run_id, dumps([pid]))).fetchone()[0]
    cur = ctx.conn.execute("INSERT INTO revision (run_id, work_id, segment_ids, version, english, variant) VALUES (?,?,?,?,?,?)",
                           (ctx.run_id, ctx.work_id, dumps([pid]), v, english, "lead"))
    eid = ctx.emit(ACTOR, "revision.created", {"segment_id": pid, "revision_id": cur.lastrowid, "version": v,
                                               "english": english, "cause": {"queries": cause}})
    ctx.conn.execute("UPDATE revision SET event_id=? WHERE id=?", (eid, cur.lastrowid))
    ctx.conn.commit()
    return cur.lastrowid


def answer(ctx, p, english: str, open_qs: list[dict], refmap: dict):
    inp = context.join(
        source_check.stable(ctx, [p]),
        context.block("The paragraph", context.referent_lines(p, refmap.get(p.id)) + f"\n  English: {english}"),
        context.block("The queries", "\n\n".join(queries.render_for_owner(q) for q in open_qs)),
    )
    return ctx.call(ACTOR, Call("translate-answer", SPARK, "low", inp, load_schema("translate-answer"),
                                f"{ctx.cache_key()}:answer", expected_output_tokens=2000))


def recheck(ctx, p, before: str, after: str, open_qs: list[dict], answers: dict, refmap: dict, round_: int) -> int:
    """The critic sees the diff and the written answers, nothing else of the owner's reasoning."""
    lines = []
    for q in open_qs:
        a = answers.get(q["id"], {})
        lines.append(f"{queries.render_for_owner(q)}\n  answer: {a.get('status', 'no answer')}: {a.get('reason', '')}")
    diff = (f"Before: {before}\nAfter:  {after}" if before != after else f"Unchanged: {before}")
    extra = context.block("This is a re-check", "Your earlier queries on this paragraph, the translator's answers, and "
                          "what changed. Close a query (raise nothing for it) if the answer settles it; raise it again "
                          "only with new evidence.\n\n" + "\n\n".join(lines) + "\n\n" + diff)
    inp = context.join(source_check.stable(ctx, [p]),
                       source_check.page_block([p], {p.id: after}, refmap, {}), extra)
    res = ctx.call(source_check.ACTOR, Call("source-check", WONDER, "low", inp, load_schema("source-check"),
                                            f"{ctx.cache_key()}:source-check", expected_output_tokens=2000))
    return source_check.record(ctx, res.data, [p], round_)


def give_up(ctx, p, q: dict, english: str, last_answer: dict) -> None:
    """Round 2 is the end: a fork on a hard paragraph, otherwise the translator's text stands, labelled."""
    if tier(ctx, p.id) == "hard":
        options = [
            {"author": q["raised_by"], "tradeoff": "", "case": q["reason"], "text": q["recommendation"]},
            {"author": "translation", "tradeoff": "", "case": last_answer.get("reason", ""), "text": english},
        ]
        cur = ctx.conn.execute(
            "INSERT INTO fork (run_id, work_id, anchor, question, options, head_pick, head_reason, status) VALUES (?,?,?,?,?,?,?,?)",
            (ctx.run_id, ctx.work_id, p.id, f"{q['category']} at “{q['span']}”", dumps(options), 1,
             "The translator's text stands until the editor rules.", "open"))
        ctx.conn.commit()
        queries.set_status(ctx, q["id"], "forked", "house")
        ctx.emit("house", "fork.opened", {"fork_id": cur.lastrowid, "anchor": p.id, "kind": "query",
                                          "query_id": q["id"], "options": options, "head_pick": 1})
    else:
        queries.set_status(ctx, q["id"], "head-pick", "house",
                           {"label": "head's pick, unresolved", "standing": english})


def run(ctx) -> dict:
    refmap = (ctx.latest("referents") or {}).get("paragraphs", {})
    stats = {"answered": 0, "accepted": 0, "stet": 0, "revised": 0, "rechecks": 0, "rechecks_skipped": 0,
             "reraised": 0, "forks": 0, "head_picks": 0, "flagged": 0}
    by_pid = {}
    for q in queries.open_queries(ctx):
        by_pid.setdefault(q["segment_id"], []).append(q)
    for pid in sorted(by_pid, key=lambda x: int(x[1:])):
        p = ctx.work.para(pid)
        while True:
            open_qs = queries.open_queries(ctx, pid)
            if not open_qs:
                break
            english = latest_english(ctx)[pid]
            if open_qs[0]["round"] >= queries.MAX_ROUNDS or revisions_by_answer(ctx, pid) >= MAX_REVISIONS:
                row = ctx.conn.execute("SELECT answer FROM query WHERE run_id=? AND segment_id=? AND answer IS NOT NULL "
                                       "ORDER BY id DESC LIMIT 1", (ctx.run_id, pid)).fetchone()
                last = json.loads(row["answer"]) if row else {}
                for q in open_qs:
                    give_up(ctx, p, q, english, last)
                    stats["forks" if tier(ctx, pid) == "hard" else "head_picks"] += 1
                break
            res = answer(ctx, p, english, open_qs, refmap)
            answers = {a["query_id"]: a for a in res.data["answers"]}
            for q in open_qs:
                a = answers.get(q["id"], {"status": "stet", "reason": "no answer given; the text stands"})
                queries.set_status(ctx, q["id"], a["status"], ACTOR, {"status": a["status"], "reason": a["reason"]},
                                   event="query.answered")
                stats[a["status"]] += 1
                stats["answered"] += 1
            after = res.data["revised_english"] or english
            if after != english:
                new_revision(ctx, pid, after, [q["id"] for q in open_qs])
            all_accepted = all(a.get("status") == "accepted" for a in answers.values()) and len(answers) >= len(open_qs)
            if all_accepted and after != english:
                # nothing to argue about: the critic was right and the fix is in; code closes the letters
                for q in open_qs:
                    ctx.emit("house", "query.resolved", {"query_id": q["id"], "segment_id": pid, "status": "accepted",
                                                         "reason": "accepted and applied; no re-check"})
                stats["rechecks_skipped"] += 1
                continue
            stats["rechecks"] += 1
            stats["reraised"] += recheck(ctx, p, english, after, open_qs, answers, refmap, open_qs[0]["round"] + 1)
    total = stats["answered"] or 1
    stats["accept_rate"] = round(stats["accepted"] / total, 2)  # near 1.0 means the answer call is a rubber stamp
    return stats
