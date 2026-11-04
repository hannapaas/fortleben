"""Event types: the only way state changes are recorded. Part of the contract between lanes.

Every change to text, queries, rules, budget or status is an event in the `event` table. The UI,
the House stream, replay and evals read events; nothing else is a source of truth. Change this
list only with a note in the commit and docs/ARCHITECTURE.md §7 updated in the same commit.

Each event has an actor (a department and role, a person, or 'house'), a type from TYPES, a
JSON payload and the cost of the call behind it, if any. Every payload that comes from a model
call carries `say`, the department's one plain sentence for the House log.
"""

import sqlite3

from house.db import dumps

TYPES = {
    # the works
    "work.added": "a work was added from an Aozora link: its id, the card, who added it, its rights record",
    "work.refused": "an Aozora link was read and refused: the card, why, who pasted it",
    # the run
    "run.started": "a run began: work, options, caps",
    "run.paused": "the run stopped after a stage (development stops, or the checkpoint)",
    "call.downgraded": "a model's answer failed twice, so the call was made again on a smaller model",
    "parts.planned": "the planner divided the book into parts for the later stages",
    "final.read": "the final read finished: its fixes, notes and verdict",
    "run.stopped": "the run stopped mid-way because the budget ran out; nothing was released",
    "run.done": "the run finished",
    "stage.started": "a stage began",
    "stage.done": "a stage finished: what it produced, its spend",
    "stage.failed": "a stage couldn't finish: the error; the run stops there and can be resumed",
    # calls and the House stream
    "call.started": "a model call went out: department, prompt, model, effort",
    "call.done": "a model call came back: tokens, cost, from cache or live",
    "agent.say": "a department's one plain sentence for the House log",
    # what the house knows
    "reading.written": "the house's reading (first read), versioned",
    "crux.checked": "the second reader's crux and whether it matches",
    "bible.written": "the story bible, versioned",
    # the checkpoint: the editor steers before the draft (docs/STEERING.md)
    "checkpoint.waiting": "the run waits for the editor: page 1 drafted in each voice take",
    "checkpoint.steered": "the house answered an editor's note: its reply, what changed, page 1 drafted again",
    "checkpoint.approved": "the editor approved the checkpoint and chose the voice the draft is written in",
    "document.edited": "the editor rewrote the reading, the voices or the bible by hand at the checkpoint: before, after, who",
    # the English
    "page.cut": "the pager's pages: paragraph ids per page",
    "draft.paragraph": "a paragraph (or group) of English landed: revision id, variant",
    "revision.created": "the English for a paragraph changed: cause (query, rule, editor); an editor's own edit of a published edition keeps before, after and who",
    "check.flagged": "a code check flagged a paragraph: which check, why",
    "chapter.read": "a reader finished a chapter: which reader, paragraph ids, notes left",
    "desk.done": "the desk finished a chapter: notes in, paragraphs changed; or skipped, with no notes",
    "disagreement.recorded": "the readers pulled opposite ways on a span: both sides, the desk's choice, sent up or not",
    # the debate
    "query.raised": "a margin note on a span: a reader's note to the desk, or a code check's",
    "query.resolved": "a note was settled: taken, declined, forked or unaddressed, with the reason",
    "fork.opened": "a choice sent up to the editor, both sides' case verbatim",
    "fork.decided": "the editor (or the head, standing) decided a fork",
    "intern.hired": "a head asked for an intern: question, reason",
    "rule.applied": "a standing rule touched these lines",
    # notes and release
    "note.written": "a note, with anchor, views and sources",
    "release.made": "an edition version was released",
}


def emit(conn: sqlite3.Connection, run_id: int | None, actor: str, type_: str, payload: dict,
         cost_usd: float = 0.0, call_id: int | None = None, commit: bool = True) -> int:
    if type_ not in TYPES:
        raise ValueError(f"unknown event type {type_!r}")
    # seq in the same statement as the insert, so two connections writing one run's events never share a number
    cur = conn.execute(
        "INSERT INTO event (run_id, seq, actor, type, payload, cost_usd, call_id) "
        "SELECT ?, COALESCE(MAX(seq), 0) + 1, ?, ?, ?, ?, ? FROM event WHERE run_id IS ?",
        (run_id, actor, type_, dumps(payload), cost_usd, call_id, run_id),
    )
    if commit:
        conn.commit()
    return cur.lastrowid
