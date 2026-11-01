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
    # the run
    "run.started": "a run began: work, options, caps",
    "run.paused": "the run stopped after a stage (development stops, or the checkpoint)",
    "run.done": "the run finished",
    "stage.started": "a stage began",
    "stage.done": "a stage finished: what it produced, its spend",
    "stage.failed": "a stage couldn't finish: the error; the run moves on or stops",
    # calls and the House stream
    "call.started": "a model call went out: department, prompt, model, effort",
    "call.done": "a model call came back: tokens, cost, from cache or live",
    "agent.say": "a department's one plain sentence for the House log",
    "budget.tick": "spend so far in drops and dollars",
    # what the house knows
    "reading.written": "the house's reading (first read), versioned",
    "crux.checked": "the second reader's crux and whether it matches",
    "bible.written": "the story bible, versioned",
    "referents.written": "referent map and tiers for a range of paragraphs",
    # the English
    "page.cut": "the pager's pages: paragraph ids per page",
    "draft.paragraph": "a paragraph (or group) of English landed: revision id, variant",
    "revision.created": "the English for a paragraph changed: cause (query, rule, editor)",
    "check.flagged": "a code check flagged a paragraph: which check, why",
    # the debate
    "query.raised": "a department raised a query on a span",
    "query.answered": "the owner answered: accepted / stet / revised",
    "query.resolved": "a query closed, or went to the head, or became a fork",
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
    seq = conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM event WHERE run_id IS ?", (run_id,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO event (run_id, seq, actor, type, payload, cost_usd, call_id) VALUES (?,?,?,?,?,?,?)",
        (run_id, seq, actor, type_, dumps(payload), cost_usd, call_id),
    )
    if commit:
        conn.commit()
    return cur.lastrowid
