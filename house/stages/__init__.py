"""Stages: one module per stage, each with run(ctx). The order is house/orchestrator.py."""

import json
import sqlite3
from dataclasses import dataclass, field

from house import events
from house.client import BaseClient, Call, Result
from house.db import dumps
from house.parser import ParsedWork


@dataclass
class Ctx:
    conn: sqlite3.Connection
    client: BaseClient
    work: ParsedWork
    run_id: int
    options: dict = field(default_factory=dict)

    @property
    def work_id(self) -> str:
        return self.work.meta["work_id"]

    def emit(self, actor: str, type_: str, payload: dict, cost_usd=0.0, call_id=None) -> int:
        return events.emit(self.conn, self.run_id, actor, type_, payload, cost_usd, call_id)

    def call(self, actor: str, call: Call) -> Result:
        """Make a call on behalf of a department, with its events: started, done, and its say line."""
        call.run_id, call.stage = self.run_id, self.options.get("_stage")
        self.emit(actor, "call.started", {"prompt": call.prompt, "model": call.model, "effort": call.effort})
        res = self.client.call(call)
        u = res.usage
        self.emit(actor, "call.done", {
            "prompt": call.prompt, "model": res.model, "effort": res.effort, "from_cache": res.from_cache,
            "input_tokens": u.input_tokens, "cached_tokens": u.cached_tokens, "output_tokens": u.output_tokens,
            "reasoning_tokens": u.reasoning_tokens, "web_searches": u.web_searches,
            "list_cost_usd": round(res.list_cost_usd, 6),
        }, cost_usd=res.cost_usd, call_id=res.call_id)
        if isinstance(res.data, dict) and res.data.get("say"):
            self.emit(actor, "agent.say", {"say": res.data["say"], "prompt": call.prompt}, call_id=res.call_id)
        return res

    # the versioned knowledge of a work: reading, crux check, bible
    def latest(self, kind: str) -> dict | None:
        return latest_document(self.conn, self.work_id, kind, self.run_id)

    def version(self, kind: str) -> int:
        return self.conn.execute("SELECT COALESCE(MAX(version), 0) FROM bible WHERE work_id=? AND kind=?",
                                 (self.work_id, kind)).fetchone()[0]

    def save(self, kind: str, body: dict, event_id: int | None = None) -> int:
        v = self.version(kind) + 1
        self.conn.execute("INSERT INTO bible (work_id, version, kind, body, event_id) VALUES (?,?,?,?,?)",
                          (self.work_id, v, kind, dumps(body), event_id))
        self.conn.commit()
        return v

    def cache_key(self) -> str:
        """One prompt_cache_key per work and bible version: a bible change starts a new cached prefix."""
        return f"{self.work_id}:bible-v{self.version('bible')}"


def latest_document(conn, work_id: str, kind: str, run_id: int | None = None) -> dict | None:
    """The latest version of one of a work's documents (reading, bible, ...). With a run, the latest
    version that run saved, if it saved one: two runs of the same work each keep their own reading and
    bible, so one editor's notes never reach another's run. Otherwise the work's latest."""
    row = None
    if run_id is not None:
        row = conn.execute("SELECT b.body FROM bible b JOIN event e ON e.id = b.event_id "
                           "WHERE b.work_id=? AND b.kind=? AND e.run_id=? ORDER BY b.version DESC LIMIT 1",
                           (work_id, kind, run_id)).fetchone()
    row = row or conn.execute("SELECT body FROM bible WHERE work_id=? AND kind=? ORDER BY version DESC LIMIT 1",
                              (work_id, kind)).fetchone()
    if not row:
        return None
    return json.loads(row["body"]) if isinstance(row["body"], str) else row["body"]
