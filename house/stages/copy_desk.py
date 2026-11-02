"""The copy desk, code only: stray scripts and
length outliers, on the current English. Everything becomes a query with the reason; nothing rewrites the base text."""

from house import checks, queries
from house.stages.common import latest_units

ACTOR = "copy-desk/code"


def run(ctx) -> dict:
    raised = 0
    already = {(r["segment_id"], r["reason"]) for r in ctx.conn.execute(
        "SELECT segment_id, reason FROM query WHERE run_id=? AND raised_by=?", (ctx.run_id, ACTOR))}
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
            queries.raise_query(ctx, pid, ACTOR, {"category": category, "reason": why, "span": None,
                                                  "confidence": "high", "say": f"Copy desk: {why}."})
            raised += 1
    return {"queries": raised}
