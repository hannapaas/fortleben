"""Stage 12: copy desk, code only in the minimal pipeline (Glimmer comes later). Ledger tokens,
doubled words where a token meets the text, stray scripts, tics and length outliers, on the
current English. Everything becomes a query with the reason; nothing rewrites the base text."""

from house import checks, queries
from house.stages.draft import latest_english
from house.stages.source_check import terms

ACTOR = "copy-desk/code"


def run(ctx) -> dict:
    english = latest_english(ctx)
    t = terms(ctx)
    raised = 0
    already = {(r["segment_id"], r["reason"]) for r in ctx.conn.execute(
        "SELECT segment_id, reason FROM query WHERE run_id=? AND raised_by=?", (ctx.run_id, ACTOR))}
    pairs = {p.id: (p.text, checks.render(english[p.id], t)) for p in ctx.work.translatable() if p.id in english}
    found = {pid: [("omission", why)] for pid, why in checks.omissions(pairs).items()}
    for pid, en in english.items():
        found.setdefault(pid, [])
        found[pid] += [("ledger", w) for w in checks.ledger(en, t)]
        found[pid] += [("other", w) for w in checks.stray_scripts(en) + checks.tics(checks.render(en, t))]
    for pid, items in found.items():
        for category, why in items:
            if (pid, why) in already:
                continue
            queries.raise_query(ctx, pid, ACTOR, {"category": category, "reason": why, "span": None,
                                                  "confidence": "high", "say": f"Copy desk: {why}."})
            raised += 1
    return {"queries": raised}
