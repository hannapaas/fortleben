"""Calls that don't depend on each other go out side by side (Ctx.side_by_side): the readers, and the
checkpoint's voice takes. What they store is the same, in the same order, as one by one."""

import _thread
import json
import threading
import time
from dataclasses import replace
from types import SimpleNamespace

import pytest

from house import events, orchestrator
from house.budget import CapExceeded
from house.client import FIXTURES, SPARK, BaseClient, Call, FakeClient, ModelClient, cache_dir
from house.db import another, connect
from house.stages import Ctx


@pytest.fixture
def ctx(tmp_path):
    conn = connect(tmp_path / "k.db")
    conn.execute("INSERT INTO work (id, aozora_id, title, author) VALUES ('w', 1, 't', 'a')")
    conn.execute("INSERT INTO run (id, work_id) VALUES (1, 'w')")
    conn.commit()
    return Ctx(conn, FakeClient(conn), None, 1, {})


def ours():
    return [t for t in threading.enumerate() if t.name.startswith("run-1-")]


@pytest.fixture(autouse=True)
def four(monkeypatch):
    monkeypatch.setenv("KEIKAKU_PARALLEL", "4")


def test_items_run_at_once_and_come_back_in_order(ctx):
    live, most, lock = [0], [0], threading.Lock()

    def fn(c, i):
        assert c.conn is not ctx.conn and c.client.conn is c.conn and c.client.budget.conn is c.conn
        with lock:
            live[0] += 1
            most[0] = max(most[0], live[0])
        time.sleep(0.05 * (5 - i))  # the first item finishes last
        with lock:
            live[0] -= 1
        return i * 10

    assert ctx.side_by_side(fn, range(5)) == [0, 10, 20, 30, 40]
    assert most[0] == 4
    assert not ours()


def test_one_at_a_time_when_asked_or_in_memory(ctx, monkeypatch):
    seen = []
    monkeypatch.setenv("KEIKAKU_PARALLEL", "1")
    assert ctx.side_by_side(lambda c, i: seen.append(c.conn is ctx.conn) or i, [1, 2]) == [1, 2]
    monkeypatch.delenv("KEIKAKU_PARALLEL")
    mem = connect(":memory:")
    assert Ctx(mem, FakeClient(mem), None, 1, {}).side_by_side(lambda c, i: seen.append(c.conn is mem) or i, [3, 4]) == [3, 4]
    assert seen == [True] * 4


def test_an_error_stops_new_items_and_is_raised_once_the_rest_finish(ctx, monkeypatch):
    monkeypatch.setenv("KEIKAKU_PARALLEL", "2")
    started, finished = [], []

    def fn(c, i):
        started.append(i)
        if i == 1:
            raise ValueError("item 1")
        time.sleep(0.1)
        finished.append(i)
        return i

    stored = []
    with pytest.raises(ValueError, match="item 1"):
        ctx.side_by_side(fn, range(6), then=lambda i, r: stored.append(r))
    assert 0 in finished  # under way when item 1 failed, so it finished
    assert len(started) < 6  # and the queue stopped
    assert stored == [0]  # what came before the error is stored, so a resume doesn't ask again
    assert not ours()


@pytest.mark.parametrize("width", ["1", "3"])
def test_then_stores_in_order_one_by_one_or_side_by_side(ctx, monkeypatch, width):
    monkeypatch.setenv("KEIKAKU_PARALLEL", width)
    stored = []
    out = ctx.side_by_side(lambda c, i: time.sleep(0.01 * (5 - i)) or i, range(5), then=lambda i, r: stored.append((i, r)))
    assert out == [0, 1, 2, 3, 4] and stored == [(i, i) for i in range(5)]


def test_ctrl_c_stops_the_queue(ctx, monkeypatch):
    monkeypatch.setenv("KEIKAKU_PARALLEL", "2")
    started = []

    def fn(c, i):
        started.append(i)
        if i == 0:
            _thread.interrupt_main()  # Ctrl-C, as it arrives on the command line
        time.sleep(0.2)
        return i

    with pytest.raises(KeyboardInterrupt):
        ctx.side_by_side(fn, range(20))
    n = len(started)  # what started before the main thread saw the interrupt (it looks every half second)
    time.sleep(0.5)  # the ones under way finish; nothing new starts
    assert n < 20 and len(started) == n and not ours()


def test_events_from_several_connections_keep_one_sequence(ctx):
    path = ctx.conn.execute("PRAGMA database_list").fetchone()["file"]

    def emit_many(k):
        conn = another(path)
        for n in range(40):
            events.emit(conn, 1, "house", "agent.say", {"say": f"{k}-{n}"})
        conn.close()

    threads = [threading.Thread(target=emit_many, args=(k,)) for k in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    seqs = [r[0] for r in ctx.conn.execute("SELECT seq FROM event WHERE run_id=1 ORDER BY seq")]
    assert seqs == list(range(1, 161))


class SlowAPI:
    """The Meta API, standing in: each response takes a moment, so calls overlap."""

    def __init__(self):
        self.responses, self.lock, self.live, self.most = self, threading.Lock(), 0, 0

    def create(self, **req):
        with self.lock:
            self.live += 1
            self.most = max(self.most, self.live)
        time.sleep(0.1)
        with self.lock:
            self.live -= 1
        return SimpleNamespace(
            id="resp", status="completed", incomplete_details=None,
            usage=SimpleNamespace(input_tokens=1000, output_tokens=500,
                                  input_tokens_details=SimpleNamespace(cached_tokens=0),
                                  output_tokens_details=SimpleNamespace(reasoning_tokens=0)),
            output=[SimpleNamespace(type="message", content=[
                SimpleNamespace(type="output_text", text=f'{{"say": "Read {req["input"]}."}}', annotations=[])])])


def test_live_calls_side_by_side_are_priced_ledgered_and_capped(ctx, monkeypatch):
    c = ModelClient.__new__(ModelClient)
    BaseClient.__init__(c, ctx.conn, cache_dirs=[cache_dir()], run_cap=1.0)
    c.api = SlowAPI()
    ctx = replace(ctx, client=c)
    schema = {"type": "object", "properties": {"say": {"type": "string"}}}

    def ask(cx, i):
        return cx.call("reader/faithful", Call("reader-faithful", SPARK, "low", f"part {i}", schema,
                                               expected_output_tokens=100)).data["say"]

    assert ctx.side_by_side(ask, range(6)) == [f"Read part {i}." for i in range(6)]
    assert c.api.most == 4
    rows = ctx.conn.execute("SELECT run_id, cost_usd FROM call ORDER BY id").fetchall()
    assert len(rows) == 6 and all(r["run_id"] == 1 and r["cost_usd"] > 0 for r in rows)
    assert c.budget.spent(1) == pytest.approx(sum(r["cost_usd"] for r in rows))
    c.budget.run_cap = c.budget.spent(1)  # no room left: every call is refused before it goes out
    with pytest.raises(CapExceeded):
        ctx.side_by_side(ask, range(6, 10))
    assert len(ctx.conn.execute("SELECT id FROM call").fetchall()) == 6


def replay(tmp_path, name, **options):
    recorded = json.loads((FIXTURES / "bansan" / "run.json").read_text(encoding="utf-8"))
    conn = connect(tmp_path / f"{name}.db")
    client = FakeClient(conn, cache_dirs=[FIXTURES / "bansan" / "responses"], run_cap=0.0)
    opts = {k: v for k, v in recorded["run"]["options"].items() if k != "pipeline"}
    return conn, orchestrator.run(conn, client, "bansan", options={**opts, **options})


def test_a_run_side_by_side_stores_what_a_run_one_by_one_does(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.setenv("KEIKAKU_PARALLEL", "1")
    one, r1 = replay(tmp_path, "one")
    monkeypatch.delenv("KEIKAKU_PARALLEL")
    many, r2 = replay(tmp_path, "many")

    def stored(conn, run_id):
        return ([tuple(r) for r in conn.execute("SELECT segment_id, raised_by, span, reason, status FROM query WHERE run_id=? ORDER BY id", (run_id,))],
                [tuple(r) for r in conn.execute("SELECT segment_ids, version, english FROM revision WHERE run_id=? ORDER BY id", (run_id,))],
                conn.execute("SELECT body FROM release WHERE run_id=?", (run_id,)).fetchone()[0])

    assert stored(one, r1) == stored(many, r2)
    seqs = [r[0] for r in many.execute("SELECT seq FROM event WHERE run_id=? ORDER BY seq", (r2,))]
    assert seqs == list(range(1, len(seqs) + 1))
    calls = many.execute("SELECT COUNT(*) FROM call WHERE run_id=? AND prompt LIKE 'reader-%'", (r2,)).fetchone()[0]
    assert calls == 2 and not ours()


def test_the_checkpoint_drafts_its_takes_side_by_side_in_order(tmp_path, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    conn, run_id = replay(tmp_path, "cp", checkpoint=True)
    doc = json.loads(conn.execute("SELECT body FROM bible WHERE kind='checkpoint'").fetchone()[0])
    reading = json.loads(conn.execute("SELECT body FROM bible WHERE kind='reading' ORDER BY version DESC").fetchone()[0])
    assert [t["label"] for t in doc["takes"]] == [t["label"] for t in reading["voice_takes"]]
    n = conn.execute("SELECT COUNT(*) FROM call WHERE run_id=? AND stage='checkpoint'", (run_id,)).fetchone()[0]
    assert n == len(reading["voice_takes"])
