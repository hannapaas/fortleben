"""Queries: the house's letters. One row each, a fixed shape, statuses changed only here,
with an event for every change (docs/STAGES.md, "How a debate actually runs")."""

import json

from house.db import dumps

MAX_PER_PARAGRAPH = 8


def raise_query(ctx, segment_id: str, raised_by: str, q: dict, round_: int = 0, owner: str = "translation") -> int:
    cur = ctx.conn.execute(
        """INSERT INTO query (run_id, work_id, segment_id, span, raised_by, owner, category, reason, evidence,
           recommendation, confidence, status, round, say) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (ctx.run_id, ctx.work_id, segment_id, q.get("span"), raised_by, owner, q["category"], q["reason"],
         dumps([q["evidence_ja"]] if q.get("evidence_ja") else []), q.get("suggested_fix"), q.get("confidence"),
         "open", round_, q.get("say")))
    qid = cur.lastrowid
    eid = ctx.emit(raised_by, "query.raised", {"query_id": qid, "segment_id": segment_id, "round": round_,
                                               "sentence": q.get("sentence"), **{k: q.get(k) for k in (
                                                   "span", "category", "reason", "evidence_ja", "confidence",
                                                   "suggested_fix", "say")}})
    ctx.conn.execute("UPDATE query SET event_id=? WHERE id=?", (eid, qid))
    ctx.conn.commit()
    return qid


def open_queries(ctx, segment_id: str | None = None) -> list[dict]:
    sql = "SELECT * FROM query WHERE run_id=? AND status='open'"
    args = [ctx.run_id]
    if segment_id:
        sql += " AND segment_id=?"
        args.append(segment_id)
    return [dict(r) for r in ctx.conn.execute(sql + " ORDER BY id", args)]


def set_status(ctx, qid: int, status: str, actor: str, answer: dict | None = None, event: str = "query.resolved") -> None:
    ctx.conn.execute("UPDATE query SET status=?, answer=COALESCE(?, answer), resolver=? WHERE id=?",
                     (status, dumps(answer) if answer else None, actor, qid))
    ctx.conn.commit()
    ctx.emit(actor, event, {"query_id": qid, "status": status, **(answer or {})})


def render_for_owner(q: dict) -> str:
    ev = "; ".join(json.loads(q["evidence"] or "[]"))
    return (f"Query {q['id']} (round {q['round']}, from {q['raised_by']}, {q['category']}, confidence {q['confidence']}):\n"
            f"  span: “{q['span']}”\n  reason: {q['reason']}\n  evidence: {ev or 'none given'}\n"
            f"  suggested fix: {q['recommendation'] or 'none'}")
