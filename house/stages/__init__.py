"""Stages: one module per stage, each with run(ctx). The order is house/orchestrator.py."""

import json
import os
import queue
import sqlite3
import threading
from dataclasses import dataclass, field, replace

from house import db, events
from house.client import BaseClient, Call, Result
from house.db import dumps
from house.parser import ParsedWork


def width() -> int:
    """How many calls a stage may have out at once: KEIKAKU_PARALLEL, default 4; 1 makes every stage serial."""
    return max(1, int(os.environ.get("KEIKAKU_PARALLEL") or 4))


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

    def loop(self, actor: str, call: Call, handle, max_turns: int = 12) -> Result:
        """A call with function tools: the model calls them, `handle(name, args)` runs each and its reply
        goes back, until the model gives its answer. Meta's API takes tool_choice "auto" only, so the
        model decides when it's done; after max_turns it's told to answer. Each turn is one call, ledgered
        and cached like any other, so a loop replays."""
        turns = []
        for n in range(max_turns + 1):
            res = self.call(actor, replace(call, turns=list(turns) or None))
            if not res.tool_calls:
                return res
            if n == max_turns:
                raise RuntimeError(f"{call.prompt}: still calling tools after {max_turns} turns")
            for tc in res.tool_calls:
                try:
                    reply = handle(tc["name"], json.loads(tc["arguments"]))
                except json.JSONDecodeError:
                    reply = "Error: the arguments weren't valid JSON."
                turns += [{"type": "function_call", "call_id": tc["call_id"], "name": tc["name"], "arguments": tc["arguments"]},
                          {"type": "function_call_output", "call_id": tc["call_id"], "output": reply}]
            if n == max_turns - 1:
                turns.append({"role": "user", "content": "That was your last turn with the tools: give your answer now."})
        raise AssertionError("unreachable")

    def side_by_side(self, fn, items, then=None) -> list:
        """fn(ctx, item) for every item, up to width() at once, and the results in the items' order. Only for
        work that doesn't depend on itself: each runs on its own connection, may make calls and emit events, and
        stores nothing. then(item, result), if given, stores a result here, in the items' order, as one by one
        would. After an error no new item starts, the ones under way finish, the items before it are stored, and
        it is raised, so no thread is left writing after the stage has stopped and a resumed stage redoes only
        what wasn't stored. The threads are daemons, and Ctrl-C stops the queue, so the command line doesn't
        wait for calls in flight. An in-memory database (some tests) runs them one by one, as does a single item."""
        items, path = list(items), db.file_of(self.conn)
        n = min(width(), len(items))
        if n <= 1 or not path:
            out = []
            for it in items:
                out.append(fn(self, it))
                if then:
                    then(it, out[-1])
            return out
        self.conn.commit()  # an open write on this connection would hold up every thread's writes
        results, errors, todo, stop = [None] * len(items), {}, queue.SimpleQueue(), threading.Event()
        for i in range(len(items)):
            todo.put(i)

        def worker():
            while not stop.is_set():
                try:
                    i = todo.get_nowait()
                except queue.Empty:
                    return
                conn = None
                try:
                    conn = db.another(path)
                    results[i] = fn(replace(self, conn=conn, client=self.client.on(conn)), items[i])
                except BaseException as e:
                    errors[i] = e
                    stop.set()
                finally:
                    if conn is not None:
                        conn.close()

        threads = [threading.Thread(target=worker, daemon=True, name=f"run-{self.run_id}-{k}") for k in range(n)]
        try:
            for t in threads:
                t.start()
            for t in threads:
                while t.is_alive():
                    t.join(0.5)  # a bare join can't be interrupted by Ctrl-C on Windows
        except BaseException:
            stop.set()
            raise
        first = min(errors) if errors else len(items)
        if then:
            for i in range(first):
                then(items[i], results[i])
        if errors:
            raise errors[first]
        return results

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
