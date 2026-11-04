"""The checkpoint, between the bible and the draft (docs/EDITORS-DESK.md). With the run's `checkpoint`
option off it does nothing. With it on, it drafts the first page once in each voice take the reading
offers, with the drafting prompt and model the run uses, keeps those drafts in the `checkpoint`
document (not as revisions: none of them is the run's English yet), and sets the run `waiting`. The
orchestrator stops there. The editor reads the takes, steers with notes (house/steer.py) and approves
a voice; the run then carries on from the draft.

Experiment 3 found that a model picking between voice trials didn't help. This isn't that: a person
is choosing, and the trial is three page drafts, the cheapest point at which to be wrong.
"""

import json

from house import pager
from house.stages import draft

ACTOR = "translation/drafter"


def english(res) -> list[list[str]]:
    """A drafted page as [[pid, english], ...]. A group the drafter joined is labelled p21–p23."""
    return [[it["ids"][0] if len(it["ids"]) == 1 else f"{it['ids'][0]}–{it['ids'][-1]}", it["english"]]
            for it in res.data["items"]]


def draft_first_page(ctx, take: dict) -> list[list[str]]:
    """Page 1 in one voice take, by the run's normal drafting call. Nothing is stored."""
    first = pager.pages(ctx.work.paragraphs)[0]
    return english(draft.draft_page(ctx, first, ctx.work.translatable(), draft.stable_for(ctx, take), ""))


def document(conn, run_id: int) -> tuple[dict | None, int]:
    """The run's latest checkpoint document and its version, or (None, 0)."""
    work_id = conn.execute("SELECT work_id FROM run WHERE id=?", (run_id,)).fetchone()["work_id"]
    for r in conn.execute("SELECT version, body FROM bible WHERE work_id=? AND kind='checkpoint' ORDER BY version DESC",
                          (work_id,)):
        body = json.loads(r["body"])
        if body.get("run_id") == run_id:
            return body, r["version"]
    return None, 0


def approved(conn, run_id: int) -> bool:
    return conn.execute("SELECT 1 FROM event WHERE run_id=? AND type='checkpoint.approved'", (run_id,)).fetchone() is not None


def run(ctx) -> dict:
    if not ctx.options.get("checkpoint"):
        return {"skipped": True}
    if approved(ctx.conn, ctx.run_id):  # a run resumed from an earlier stage doesn't ask again
        return {"skipped": True, "approved": True}
    takes = ctx.side_by_side(lambda c, t: {"label": t["label"], "line": t["line"], "english": draft_first_page(c, t)},
                             ctx.latest("reading")["voice_takes"])  # each take's page is independent of the others
    before, _ = document(ctx.conn, ctx.run_id)
    doc = {"run_id": ctx.run_id, "takes": takes, "rounds": before["rounds"] if before else []}
    eid = ctx.emit("house", "checkpoint.waiting", {"takes": takes})
    ctx.save("checkpoint", doc, eid)
    ctx.conn.execute("UPDATE run SET status='waiting', stage='checkpoint' WHERE id=?", (ctx.run_id,))
    ctx.conn.commit()
    return {"waiting": True, "takes": len(takes)}
